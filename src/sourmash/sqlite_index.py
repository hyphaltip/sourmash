"""Provide SqliteIndex, a sqlite3-based Index class for storing and searching
sourmash signatures.

Note that SqliteIndex supports both storage and fast _search_ of scaled
signatures, via a reverse index.

Features and limitations:

* Currently we try to maintain only one database connection.  It's not 100%
  clear what happens if the same database is opened by multiple independent
  processes and one or more of them write to it. It should all work, because
  SQL...

* Unlike LCA_Database, SqliteIndex supports multiple ksizes and moltypes.

* SqliteIndex does not support 'num' signatures. It could store them easily, but
  since it cannot search them properly with 'find', we've omitted them.

* Likewise, SqliteIndex does not support 'abund' signatures because it cannot
  search them (just like SBTs cannot).

"""
import time
import sqlite3
from collections import Counter

from bitstring import BitArray

# @CTB add DISTINCT to sketch and hash select

from .index import Index
import sourmash
from sourmash import MinHash, SourmashSignature
from sourmash.index import IndexSearchResult
from .picklist import PickStyle

# converters for unsigned 64-bit ints: if over MAX_SQLITE_INT,
# convert to signed int.

MAX_SQLITE_INT = 2 ** 63 - 1
convert_hash_to = lambda x: BitArray(uint=x, length=64).int if x > MAX_SQLITE_INT else x
convert_hash_from = lambda x: BitArray(int=x, length=64).uint if x < 0 else x

picklist_transforms = dict(
    name=lambda x: x,
    ident=lambda x: x + ' %',
    identprefix=lambda x: x + '%',
    md5short=lambda x: x[:8] + '%',
    md5prefix8=lambda x: x[:8] + '%',
    md5=lambda x: x,
    )

picklist_selects = dict(
    name='INSERT INTO pickset SELECT id FROM sketches WHERE name=?',
    ident='INSERT INTO pickset SELECT id FROM sketches WHERE name LIKE ?',
    identprefix='INSERT INTO pickset SELECT id FROM sketches WHERE name LIKE ?',
    md5short='INSERT INTO pickset SELECT id FROM sketches WHERE md5sum LIKE ?',
    md5prefix8='INSERT INTO pickset SELECT id FROM sketches WHERE md5sum LIKE ?',
    md5='INSERT INTO pickset SELECT id FROM sketches WHERE md5sum=?',
    )


class SqliteIndex(Index):
    is_database = True
    
    def __init__(self, dbfile, selection_dict=None, conn=None):
        self.dbfile = dbfile
        self.selection_dict = selection_dict

        if conn is not None:
            self.conn = conn
        else:
            try:
                self.conn = sqlite3.connect(dbfile,
                                            detect_types=sqlite3.PARSE_DECLTYPES)

                c = self.conn.cursor()

                c.execute("PRAGMA cache_size=10000000")
                c.execute("PRAGMA synchronous = OFF")
                c.execute("PRAGMA journal_mode = MEMORY")
                c.execute("PRAGMA temp_store = MEMORY")

                c.execute("""
                CREATE TABLE IF NOT EXISTS sketches
                  (id INTEGER PRIMARY KEY,
                   name TEXT,
                   scaled INTEGER NOT NULL,
                   ksize INTEGER NOT NULL,
                   filename TEXT,
                   is_dna BOOLEAN NOT NULL,
                   is_protein BOOLEAN NOT NULL,
                   is_dayhoff BOOLEAN NOT NULL,
                   is_hp BOOLEAN NOT NULL,
                   md5sum TEXT NOT NULL, 
                   seed INTEGER NOT NULL
                )
                """)
                c.execute("""
                CREATE TABLE IF NOT EXISTS hashes (
                   hashval INTEGER NOT NULL,
                   sketch_id INTEGER NOT NULL,
                   FOREIGN KEY (sketch_id) REFERENCES sketches (id)
                )
                """)
                c.execute("""
                CREATE INDEX IF NOT EXISTS hashval_idx ON hashes (
                   hashval,
                   sketch_id
                )
                """)
            except (sqlite3.OperationalError, sqlite3.DatabaseError):
                raise
                raise ValueError(f"cannot open '{dbfile}' as sqlite3 database")

        c = self.conn.cursor()
        c.execute("SELECT DISTINCT scaled FROM sketches")
        scaled_vals = c.fetchall()
        if len(scaled_vals) > 1:
            raise ValueError("this database has multiple scaled values, which is not currently allowed")

        if scaled_vals:
            self.scaled = scaled_vals[0][0]
        else:
            self.scaled = None

    def cursor(self):
        return self.conn.cursor()

    def close(self):
        self.conn.close()

    def commit(self):
        self.conn.commit()

    def __len__(self):
        c = self.cursor()
        conditions, values, picklist = self._select_signatures(c)

        c.execute(f"SELECT COUNT(*) FROM sketches {conditions}", values)
        count, = c.fetchone()
        return count

    def insert(self, ss, cursor=None, commit=True):
        if cursor:
            c = cursor
        else:
            c = self.conn.cursor()

        if ss.minhash.num:
            raise ValueError("cannot store 'num' signatures in SqliteIndex")
        if ss.minhash.track_abundance:
            raise ValueError("cannot store signatures with abundance in SqliteIndex")

        if self.scaled is not None and self.scaled != ss.minhash.scaled:
            raise ValueError("this database can only store scaled values = {self.scaled}")
        elif self.scaled is None:
            self.scaled = ss.minhash.scaled

        c.execute("""
        INSERT INTO sketches
          (name, scaled, ksize, filename, md5sum,
           is_dna, is_protein, is_dayhoff, is_hp, seed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ss.name, ss.minhash.scaled, ss.minhash.ksize,
         ss.filename, ss.md5sum(),
         ss.minhash.is_dna, ss.minhash.is_protein, ss.minhash.dayhoff,
         ss.minhash.hp, ss.minhash.seed))

        c.execute("SELECT last_insert_rowid()")
        sketch_id, = c.fetchone()

        hashes = []
        hashes_to_sketch = []
        for h in ss.minhash.hashes:
            hh = convert_hash_to(h)
            hashes_to_sketch.append((hh, sketch_id))

        c.executemany("INSERT INTO hashes (hashval, sketch_id) VALUES (?, ?)", hashes_to_sketch)

        if commit:
            self.conn.commit()

    @property
    def location(self):
        return self.dbfile

    def _select_signatures(self, c):
        conditions = []
        values = []
        picklist = None
        if self.selection_dict:
            select_d = self.selection_dict
            if 'ksize' in select_d and select_d['ksize']:
                conditions.append("sketches.ksize = ?")
                values.append(select_d['ksize'])
            if 'scaled' in select_d and select_d['scaled'] > 0:
                conditions.append("sketches.scaled > 0")
            if 'containment' in select_d and select_d['containment']:
                conditions.append("sketches.scaled > 0")
            if 'moltype' in select_d:
                moltype = select_d['moltype']
                if moltype == 'DNA':
                    conditions.append("sketches.is_dna")
                elif moltype == 'protein':
                    conditions.append("sketches.is_protein")
                elif moltype == 'dayhoff':
                    conditions.append("sketches.is_dayhoff")
                elif moltype == 'hp':
                    conditions.append("sketches.is_hp")

            picklist = select_d.get('picklist')

            # support picklists!
            if picklist is not None:
                c.execute("DROP TABLE IF EXISTS pickset")
                c.execute("CREATE TABLE pickset (sketch_id INTEGER)")

                transform = picklist_transforms[picklist.coltype]
                sql_stmt = picklist_selects[picklist.coltype]

                vals = [ (transform(v),) for v in picklist.pickset ]
                c.executemany(sql_stmt, vals)

                if picklist.pickstyle == PickStyle.INCLUDE:
                    conditions.append("""
                    sketches.id IN (SELECT sketch_id FROM pickset)
                    """)
                elif picklist.pickstyle == PickStyle.EXCLUDE:
                    conditions.append("""
                    sketches.id NOT IN (SELECT sketch_id FROM pickset)
                    """)

        if conditions:
            conditions = "WHERE " + " AND ".join(conditions)
        else:
            conditions = ""

        return conditions, values, picklist

    def signatures(self):
        "Return an iterator over all signatures in the Index object."
        for ss, loc in self.signatures_with_location():
            yield ss

    def signatures_with_location(self):
        "Return an iterator over tuples (signature, location) in the Index."
        c = self.conn.cursor()
        c2 = self.conn.cursor()

        conditions, values, picklist = self._select_signatures(c)

        c.execute(f"""
        SELECT id, name, scaled, ksize, filename, is_dna, is_protein,
        is_dayhoff, is_hp, seed FROM sketches {conditions}""",
                  values)

        for ss, loc, iloc in self._load_sketches(c, c2):
            if picklist is None or ss in picklist:
                yield ss, loc

    def _signatures_with_internal(self):
        """Return an iterator of tuples (ss, location, internal_location).

        This is an internal API for use in generating manifests, and may
        change without warning.

        This method should be implemented separately for each Index object.
        """
        c = self.conn.cursor()
        c2 = self.conn.cursor()

        c.execute("""
        SELECT id, name, scaled, ksize, filename, is_dna, is_protein,
        is_dayhoff, is_hp, seed FROM sketches
        """)
        
        for ss, loc, iloc in self._load_sketches(c, c2):
            yield ss, loc, iloc

    def _load_sketch_size(self, c1, sketch_id, max_hash):
        if max_hash <= MAX_SQLITE_INT:
            c1.execute("SELECT COUNT(hashval) FROM hashes WHERE sketch_id=? AND hashval >= 0 AND hashval <= ?",
                       (sketch_id, max_hash))
        else:
            c1.execute('SELECT COUNT(hashval) FROM hashes WHERE sketch_id=?', (sketch_id,))

        n_hashes, = c1.fetchone()
        return n_hashes


    def _load_sketch(self, c1, sketch_id, *, match_scaled=None):
        # here, c1 should already have run an appropriate 'select' on 'sketches'
        # c2 will be used to load the hash values.
        c1.execute("""
        SELECT id, name, scaled, ksize, filename, is_dna, is_protein,
        is_dayhoff, is_hp, seed FROM sketches WHERE id=?""",
                   (sketch_id,))

        (sketch_id, name, scaled, ksize, filename, is_dna,
         is_protein, is_dayhoff, is_hp, seed) = c1.fetchone()
        if match_scaled is not None:
            scaled = max(scaled, match_scaled)

        mh = MinHash(n=0, ksize=ksize, scaled=scaled, seed=seed,
                     is_protein=is_protein, dayhoff=is_dayhoff, hp=is_hp)


        template_values = [sketch_id]

        hash_constraint_str = ""
        max_hash = mh._max_hash
        if max_hash <= MAX_SQLITE_INT:
            hash_constraint_str = "hashes.hashval >= 0 AND hashes.hashval <= ? AND"
            template_values.insert(0, max_hash)
        else:
            print('NOT EMPLOYING hash_constraint_str')

        c1.execute(f"SELECT hashval FROM hashes WHERE {hash_constraint_str} hashes.sketch_id=?", template_values)

        for hashval, in c1:
            hh = convert_hash_from(hashval)
            mh.add_hash(hh)

        ss = SourmashSignature(mh, name=name, filename=filename)
        return ss

    def _load_sketches(self, c1, c2):
        # here, c1 should already have run an appropriate 'select' on 'sketches'
        # c2 will be used to load the hash values.
        for (sketch_id, name, scaled, ksize, filename, is_dna, is_protein,
             is_dayhoff, is_hp, seed) in c1:
            mh = MinHash(n=0, ksize=ksize, scaled=scaled, seed=seed,
                         is_protein=is_protein, dayhoff=is_dayhoff, hp=is_hp)
            c2.execute("SELECT hashval FROM hashes WHERE sketch_id=?",
                       (sketch_id,))

            hashvals = c2.fetchall()
            for hashval, in hashvals:
                mh.add_hash(convert_hash_from(hashval))

            ss = SourmashSignature(mh, name=name, filename=filename)
            yield ss, self.dbfile, sketch_id

    def _get_matching_sketches(self, c, hashes, max_hash):
        c.execute("DROP TABLE IF EXISTS hash_query")
        c.execute("CREATE TEMPORARY TABLE hash_query (hashval INTEGER PRIMARY KEY)")

        hashvals = [ (convert_hash_to(h),) for h in hashes ]
        c.executemany("INSERT OR IGNORE INTO hash_query (hashval) VALUES (?)", hashvals)

        template_values = []

        # optimize select?
        max_hash = min(max_hash, max(hashes))
        hash_constraint_str = ""
        if max_hash <= MAX_SQLITE_INT:
            hash_constraint_str = "hashes.hashval >= 0 AND hashes.hashval <= ? AND"
            template_values.append(max_hash)

        # @CTB do we want to add select stuff on here?
        c.execute(f"""
        SELECT DISTINCT hashes.sketch_id,COUNT(hashes.hashval) FROM hashes,hash_query
        WHERE {hash_constraint_str} hashes.hashval=hash_query.hashval GROUP BY hashes.sketch_id""", template_values)

        return c

    def save(self, *args, **kwargs):
        raise NotImplementedError

    @classmethod
    def load(self, dbfile):
        return SqliteIndex(dbfile)

    def find(self, search_fn, query, **kwargs):
        search_fn.check_is_compatible(query)

        # check compatibility, etc.
        query_mh = query.minhash
        if self.scaled > query_mh.scaled:
            query_mh = query_mh.downsample(scaled=self.scaled)

        picklist = None
        if self.selection_dict:
            picklist = self.selection_dict.get('picklist')

        c1 = self.conn.cursor()
        c2 = self.conn.cursor()

        xx = self._get_matching_sketches(c1, query_mh.hashes,
                                         query_mh._max_hash)
        for sketch_id, n_matching_hashes in xx:
            query_size = len(query_mh)
            subj_size = self._load_sketch_size(c2, sketch_id,
                                               query_mh._max_hash)
            total_size = query_size + subj_size - n_matching_hashes
            shared_size = n_matching_hashes

            score = search_fn.score_fn(query_size, shared_size, subj_size,
                                       total_size)
            print('APPROX RESULT:', score, query_size, subj_size,
                  total_size, shared_size)

            if not search_fn.passes(score):
                print('FAIL')
                continue

            start = time.time()
            subj = self._load_sketch(c2, sketch_id,
                                     match_scaled=query_mh.scaled)
            print(f'LOAD SKETCH s={time.time() - start}')

            subj_mh = subj.minhash
            assert subj_mh.scaled == query_mh.scaled

            # all numbers calculated after downsampling --
            query_size = len(query_mh)
            subj_size = len(subj_mh)
            shared_size, total_size = query_mh.intersection_and_union_size(subj_mh)

            score = search_fn.score_fn(query_size, shared_size, subj_size,
                                       total_size)
            print('ACTUAL RESULT:', score, query_size, subj_size,
                  total_size, shared_size)

            if search_fn.passes(score):
                if search_fn.collect(score, subj):
                    if picklist is None or subj in picklist:
                        actual_subj = self._load_sketch(c2, sketch_id)
                        yield IndexSearchResult(score, actual_subj,
                                                self.location)

    def select(self, *, num=0, track_abundance=False, **kwargs):
        if num:
            # @CTB testme
            raise ValueError("cannot select on 'num' in SqliteIndex")
        if track_abundance:
            # @CTB testme
            raise ValueError("cannot store or search signatures with abundance")

        # Pass along all the selection kwargs to a new instance
        if self.selection_dict:
            # combine selects...
            d = dict(self.selection_dict)
            for k, v in kwargs.items():
                if k in d:
                    if d[k] is not None and d[k] != v:
                        raise ValueError(f"incompatible select on '{k}'")
                d[k] = v
            kwargs = d

        return SqliteIndex(self.dbfile, selection_dict=kwargs, conn=self.conn)