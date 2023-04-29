"""A library for creating k-mer sketches from biological sequences, comparing
them to each other, and working with the results.

Public API:

    load_file_as_signatures(...) - load `[SourmashSignature, ]` from filename
    load_file_as_index(...) - load collections of `SourmashSignature`s
    save_signatures(...) - save `[SourmashSignature, ]`

    class SourmashSignature - one or more hash sketches
    class MinHash - hash sketch class

Please see https://sourmash.readthedocs.io/en/latest/api.html for API docs.

The sourmash code is available at github.com/sourmash-bio/sourmash/ under the
BSD 3-Clause license.
"""
from deprecation import deprecated

try:
    from importlib.metadata import version
except ModuleNotFoundError:
    from importlib_metadata import version

__all__ = ['MinHash', 'SourmashSignature',
           'load_one_signature',
           'SourmashSignature',
           'load_file_as_index',
           'load_file_as_signatures',
           'save_signatures',
           'create_sbt_index',
           'load_signatures',     # deprecated - remove in 5.0
           'load_sbt_index',      # deprecated - remove in 5.0
           'search_sbt_index',    # deprecated - remove in 5.0
          ]

from ._lowlevel import ffi, lib

ffi.init_once(lib.sourmash_init, "init")

VERSION = version(__name__)

from .minhash import MinHash, get_minhash_default_seed, get_minhash_max_hash

DEFAULT_SEED = get_minhash_default_seed()
MAX_HASH = get_minhash_max_hash()

from .signature import (
    load_signatures as load_signatures_private,
    load_one_signature,
    SourmashSignature,
    save_signatures,
)

@deprecated(deprecated_in="3.5.1", removed_in="5.0",
            current_version=VERSION,
            details='Use load_file_as_signatures instead.')
def load_signatures(*args, **kwargs):
    """Load a JSON string with signatures into classes.

    Returns list of SourmashSignature objects.

    Note, the order is not necessarily the same as what is in the source file.

    This function has been deprecated as of 3.5.1; please use
    'load_file_as_signatures' instead. Note that in 4.0, the 'quiet' argument
    has been removed and the function no longer outputs to stderr.
    Moreover, do_raise is now True by default.
    """
    return load_signatures_private(*args, **kwargs)

from .sbtmh import load_sbt_index as load_sbt_index_private
from .sbtmh import search_sbt_index as search_sbt_index_private

@deprecated(deprecated_in="3.5.1", removed_in="5.0",
            current_version=VERSION,
            details='Use load_file_as_index instead.')
def load_sbt_index(*args, **kwargs):
    """Load and return an SBT index.

    This function has been deprecated as of 3.5.1; please use
    'load_file_as_index' instead.
    """
    return load_sbt_index_private(*args, **kwargs)


@deprecated(deprecated_in="3.5.1", removed_in="5.0",
            current_version=VERSION,
            details='Use the new Index API instead.')
def search_sbt_index(*args, **kwargs):
    """\
    Search an SBT index `tree` with signature `query` for matches above
    `threshold`.

    Usage:

        for match_sig, similarity in search_sbt_index(tree, query, threshold):
           ...

    This function has been deprecated as of 3.5.1; please use
    'idx = load_file_as_index(...); idx.search(query, threshold=...)' instead.
    """
    return search_sbt_index_private(*args, **kwargs)

from .sbtmh import create_sbt_index
from . import lca
from . import tax
from . import sbt
from . import sbtmh
from . import sbt_storage
from . import signature
from . import sig
from . import cli
from . import commands
from .sourmash_args import load_file_as_index
from .sourmash_args import load_file_as_signatures
