"""
Tests for functions in taxonomy submodule.
"""
import pytest
from os.path import basename

import sourmash_tst_utils as utils

from sourmash.tax.tax_utils import (ascending_taxlist, get_ident, load_gather_results,
                                    summarize_gather_at, find_missing_identities,
                                    write_summary, load_taxonomy_csv,
                                    collect_gather_csvs, check_and_load_gather_csvs,
                                    SummarizedGatherResult, ClassificationResult,
                                    write_classifications,
                                    aggregate_by_lineage_at_rank,
                                    make_krona_header, format_for_krona, write_krona,
                                    combine_sumgather_csvs_by_lineage, write_lineage_sample_frac)

# import lca utils as needed for now
from sourmash.lca import lca_utils
from sourmash.lca.lca_utils import LineagePair

#from sourmash.lca.command_index import load_taxonomy_assignments

# utility functions for testing
def make_mini_gather_results(g_infolist):
    # make mini gather_results
    min_header = ["query_name", "name", "match_ident", "f_unique_weighted", "query_md5", "query_filename"]
    gather_results = []
    for g_info in g_infolist:
        inf = dict(zip(min_header, g_info))
        gather_results.append(inf)
    return gather_results


def make_mini_taxonomy(tax_info):
    #pass in list of tuples: (name, lineage)
    taxD = {}
    for (name,lin) in tax_info:
        taxD[name] = lca_utils.make_lineage(lin)
    return taxD


## tests
def test_ascending_taxlist_1():
    assert list(ascending_taxlist()) ==  ['strain', 'species', 'genus', 'family', 'order', 'class', 'phylum', 'superkingdom']


def test_ascending_taxlist_2():
    assert list(ascending_taxlist(include_strain=False)) ==  ['species', 'genus', 'family', 'order', 'class', 'phylum', 'superkingdom']


def test_get_ident_default():
    ident = "GCF_001881345.1"
    n_id = get_ident(ident)
    assert n_id == "GCF_001881345"


def test_get_ident_split_but_keep_version():
    ident = "GCF_001881345.1"
    n_id = get_ident(ident, keep_identifier_versions=True)
    assert n_id == "GCF_001881345.1"


def test_get_ident_no_split():
    ident = "GCF_001881345.1 secondname"
    n_id = get_ident(ident, split_identifiers=False)
    assert n_id == "GCF_001881345.1 secondname"


def test_collect_gather_csvs(runtmp):
    g_csv = utils.get_test_data('tax/test1.gather.csv')
    from_file = runtmp.output("tmp-from-file.txt")
    with open(from_file, 'w') as fp:
        fp.write(f"{g_csv}\n")

    gather_files = collect_gather_csvs([g_csv], from_file=from_file)
    print("gather_files: ", gather_files)
    assert len(gather_files) == 1
    assert basename(gather_files[0]) == 'test1.gather.csv'


def test_check_and_load_gather_csvs_empty(runtmp):
    g_res = runtmp.output('empty.gather.csv')
    with open(g_res, 'w') as fp:
        fp.write("")
    csvs = [g_res]
    # load taxonomy csv
    taxonomy_csv = utils.get_test_data('tax/test.taxonomy.csv')
    tax_assign, num_rows, ranks = load_taxonomy_csv(taxonomy_csv, split_identifiers=True)
    print(tax_assign)
    # check gather results and missing ids
    with pytest.raises(Exception) as exc:
        gather_results, ids_missing, n_missing, header = check_and_load_gather_csvs(csvs, tax_assign)
        assert "No gather results loaded from" in str(exc.value)


def test_check_and_load_gather_csvs_with_empty_force(runtmp):
    g_csv = utils.get_test_data('tax/test1.gather.csv')
    #  make gather results with taxonomy name not in tax_assign
    g_res2 = runtmp.output('gA.gather.csv')
    g_results = [x.replace("GCF_001881345.1", "gA") for x in open(g_csv, 'r')]
    with open(g_res2, 'w') as fp:
        for line in g_results:
            fp.write(line)
    # make empty gather results
    g_res3 = runtmp.output('empty.gather.csv')
    with open(g_res3, 'w') as fp:
        fp.write("")

    csvs = [g_res2, g_res3]

    # load taxonomy csv
    taxonomy_csv = utils.get_test_data('tax/test.taxonomy.csv')
    tax_assign, num_rows, ranks = load_taxonomy_csv(taxonomy_csv, split_identifiers=True)
    print(tax_assign)
    # check gather results and missing ids
    gather_results, ids_missing, n_missing, header = check_and_load_gather_csvs(csvs, tax_assign, force=True)
    assert len(gather_results) == 4
    print("n_missing: ", n_missing)
    print("ids_missing: ", ids_missing)
    assert n_missing == 1
    assert ids_missing == {"gA"}


def test_check_and_load_gather_csvs_fail_on_missing(runtmp):
    g_csv = utils.get_test_data('tax/test1.gather.csv')
    # make gather results with taxonomy name not in tax_assign
    g_res2 = runtmp.output('gA.gather.csv')
    g_results = [x.replace("GCF_001881345.1", "gA") for x in open(g_csv, 'r')]
    with open(g_res2, 'w') as fp:
        for line in g_results:
            fp.write(line)

    csvs = [g_res2]

    # load taxonomy csv
    taxonomy_csv = utils.get_test_data('tax/test.taxonomy.csv')
    tax_assign, num_rows, ranks = load_taxonomy_csv(taxonomy_csv, split_identifiers=True)
    print(tax_assign)
    # check gather results and missing ids
    with pytest.raises(ValueError) as exc:
        gather_results, ids_missing, n_missing, header = check_and_load_gather_csvs(csvs, tax_assign, fail_on_missing_taxonomy=True, force=True)
    assert "Failing on missing taxonomy" in str(exc)


def test_load_gather_results():
    gather_csv = utils.get_test_data('tax/test1.gather.csv')
    gather_results, header, seen_queries = load_gather_results(gather_csv)
    assert len(gather_results) == 4


def test_load_gather_results_bad_header(runtmp):
    g_csv = utils.get_test_data('tax/test1.gather.csv')

    bad_g_csv = runtmp.output('g.csv')

    #creates bad gather result
    bad_g = [x.replace("f_unique_weighted", "nope") for x in open(g_csv, 'r')]
    with open(bad_g_csv, 'w') as fp:
        for line in bad_g:
            fp.write(line)
    print("bad_gather_results: \n", bad_g)

    with pytest.raises(ValueError) as exc:
        gather_results, header = load_gather_results(bad_g_csv)
    assert f'Not all required gather columns are present in {bad_g_csv}.' in str(exc.value)


def test_load_gather_results_empty(runtmp):
    empty_csv = runtmp.output('g.csv')

    #creates empty gather result
    with open(empty_csv, 'w') as fp:
        fp.write('')

    with pytest.raises(ValueError) as exc:
        gather_results, header = load_gather_results(empty_csv)
    assert f'Cannot read gather results from {empty_csv}. Is file empty?' in str(exc.value)


def test_load_taxonomy_csv():
    taxonomy_csv = utils.get_test_data('tax/test.taxonomy.csv')
    tax_assign, num_rows, ranks = load_taxonomy_csv(taxonomy_csv)
    print("taxonomy assignments: \n", tax_assign)
    assert list(tax_assign.keys()) == ['GCF_001881345.1', 'GCF_009494285.1', 'GCF_013368705.1', 'GCF_003471795.1', 'GCF_000017325.1']
    assert num_rows == 5 # should have read 5 rows


def test_load_taxonomy_csv_split_id():
    taxonomy_csv = utils.get_test_data('tax/test.taxonomy.csv')
    tax_assign, num_rows, ranks = load_taxonomy_csv(taxonomy_csv, split_identifiers=True)
    print("taxonomy assignments: \n", tax_assign)
    assert list(tax_assign.keys()) == ['GCF_001881345', 'GCF_009494285', 'GCF_013368705', 'GCF_003471795', 'GCF_000017325']
    assert num_rows == 5 # should have read 4 rows


def test_load_taxonomy_csv_with_ncbi_id(runtmp):
    taxonomy_csv = utils.get_test_data('tax/test.taxonomy.csv')
    upd_csv = runtmp.output("updated_taxonomy.csv")
    with open(upd_csv, 'w') as new_tax:
        tax = [x.rstrip() for x in open(taxonomy_csv, 'r')]
        ncbi_id = "ncbi_id after_space"
        fake_lin = [ncbi_id] + ["sk", "phy", "cls", "ord", "fam", "gen", "sp"]
        ncbi_tax = ",".join(fake_lin)
        tax.append(ncbi_tax)
        new_tax.write("\n".join(tax))

    tax_assign, num_rows, ranks = load_taxonomy_csv(upd_csv)
    print("taxonomy assignments: \n", tax_assign)
    assert list(tax_assign.keys()) == ['GCF_001881345.1', 'GCF_009494285.1', 'GCF_013368705.1', 'GCF_003471795.1', 'GCF_000017325.1', "ncbi_id after_space"]
    assert num_rows == 6  # should have read 6 rows


def test_load_taxonomy_csv_split_id_ncbi(runtmp):
    taxonomy_csv = utils.get_test_data('tax/test.taxonomy.csv')
    upd_csv = runtmp.output("updated_taxonomy.csv")
    with open(upd_csv, 'w') as new_tax:
        tax = [x.rstrip() for x in open(taxonomy_csv, 'r')]
        ncbi_id = "ncbi_id after_space"
        fake_lin = [ncbi_id] + ["sk", "phy", "cls", "ord", "fam", "gen", "sp"]
        ncbi_tax = ",".join(fake_lin)
        tax.append(ncbi_tax)
        new_tax.write("\n".join(tax))

    tax_assign, num_rows, ranks = load_taxonomy_csv(upd_csv, split_identifiers=True)
    print("taxonomy assignments: \n", tax_assign)
    assert list(tax_assign.keys()) == ['GCF_001881345', 'GCF_009494285', 'GCF_013368705', 'GCF_003471795', 'GCF_000017325', "ncbi_id"]
    assert num_rows == 6 # should have read 5 rows


def test_load_taxonomy_csv_duplicate(runtmp):
    taxonomy_csv = utils.get_test_data('tax/test.taxonomy.csv')
    duplicated_csv = runtmp.output("duplicated_taxonomy.csv")
    with open(duplicated_csv, 'w') as dup:
        tax = [x.rstrip() for x in open(taxonomy_csv, 'r')]
        tax.append(tax[1]) # add first tax_assign again
        dup.write("\n".join(tax))

    with pytest.raises(Exception) as exc:
        tax_assign, num_rows, ranks = load_taxonomy_csv(duplicated_csv)
        assert str(exc.value == "multiple lineages for identifier GCF_001881345.1")


def test_load_taxonomy_csv_duplicate_force(runtmp):
    taxonomy_csv = utils.get_test_data('tax/test.taxonomy.csv')
    duplicated_csv = runtmp.output("duplicated_taxonomy.csv")
    with open(duplicated_csv, 'w') as dup:
        tax = [x.rstrip() for x in open(taxonomy_csv, 'r')]
        tax.append(tax[1]) # add first tax_assign again
        dup.write("\n".join(tax))

    # now force
    tax_assign, num_rows, ranks = load_taxonomy_csv(duplicated_csv, force=True)
    print("taxonomy assignments: \n", tax_assign)
    assert list(tax_assign.keys()) == ['GCF_001881345.1', 'GCF_009494285.1', 'GCF_013368705.1', 'GCF_003471795.1', 'GCF_000017325.1']
    assert num_rows == 6 # should have read 6 rows


def test_find_missing_identities():
    # make gather results
    gA = ["queryA", "gA","0.5","0.5", "queryA_md5", "queryA.sig"]
    gB = ["queryA", "gB","0.3","0.5", "queryA_md5", "queryA.sig"]
    g_res = make_mini_gather_results([gA,gB])

    # make mini taxonomy
    gA_tax = ("gA", "a;b;c")
    taxD = make_mini_taxonomy([gA_tax])

    n, ids = find_missing_identities(g_res, taxD)
    print("n_missing: ", n)
    print("ids_missing: ", ids)
    assert n == 1
    assert ids == {"gB"}


def test_summarize_gather_at_0():
    """test two matches, equal f_unique_weighted"""
    # make gather results
    gA = ["queryA", "gA","0.5","0.5", "queryA_md5", "queryA.sig"]
    gB = ["queryA", "gB","0.3","0.5", "queryA_md5", "queryA.sig"]
    g_res = make_mini_gather_results([gA,gB])

    # make mini taxonomy
    gA_tax = ("gA", "a;b;c")
    gB_tax = ("gB", "a;b;d")
    taxD = make_mini_taxonomy([gA_tax,gB_tax])

    # run summarize_gather_at and check results!
    sk_sum, _ = summarize_gather_at("superkingdom", taxD, g_res)

    # superkingdom
    assert len(sk_sum) == 1
    print("superkingdom summarized gather: ", sk_sum[0])
    assert sk_sum[0].query_name == "queryA"
    assert sk_sum[0].query_md5 == "queryA_md5"
    assert sk_sum[0].query_filename == "queryA.sig"
    assert sk_sum[0].rank == 'superkingdom'
    assert sk_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),)
    assert sk_sum[0].fraction == 1.0

    # phylum
    phy_sum, _ = summarize_gather_at("phylum", taxD, g_res)
    print("phylum summarized gather: ", phy_sum[0])
    assert len(phy_sum) == 1
    assert phy_sum[0].query_name == "queryA"
    assert phy_sum[0].query_md5 == "queryA_md5"
    assert phy_sum[0].query_filename == "queryA.sig"
    assert phy_sum[0].rank == 'phylum'
    assert phy_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),LineagePair(rank='phylum', name='b'))
    assert phy_sum[0].fraction == 1.0
    # class
    cl_sum, _ = summarize_gather_at("class", taxD, g_res)
    assert len(cl_sum) == 2
    print("class summarized gather: ", cl_sum)
    assert cl_sum[0].query_name == "queryA"
    assert cl_sum[0].query_md5 == "queryA_md5"
    assert cl_sum[0].query_filename == "queryA.sig"
    assert cl_sum[0].rank == 'class'
    assert cl_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),
                                 LineagePair(rank='phylum', name='b'),
                                 LineagePair(rank='class', name='c'))
    assert cl_sum[0].fraction == 0.5
    assert cl_sum[1].rank == 'class'
    assert cl_sum[1].lineage == (LineagePair(rank='superkingdom', name='a'),
                                 LineagePair(rank='phylum', name='b'),
                                 LineagePair(rank='class', name='d'))
    assert cl_sum[1].fraction == 0.5


def test_summarize_gather_at_1():
    """test two matches, diff f_unique_weighted"""
    # make mini gather_results
    gA = ["queryA", "gA","0.5","0.6", "queryA_md5", "queryA.sig"]
    gB = ["queryA", "gB","0.3","0.1", "queryA_md5", "queryA.sig"]
    g_res = make_mini_gather_results([gA,gB])

    # make mini taxonomy
    gA_tax = ("gA", "a;b;c")
    gB_tax = ("gB", "a;b;d")
    taxD = make_mini_taxonomy([gA_tax,gB_tax])
    # run summarize_gather_at and check results!
    sk_sum, _ = summarize_gather_at("superkingdom", taxD, g_res)

    # superkingdom
    assert len(sk_sum) == 1
    print("superkingdom summarized gather: ", sk_sum[0])
    assert sk_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),)
    assert sk_sum[0].fraction == 0.7

    # phylum
    phy_sum, _ = summarize_gather_at("phylum", taxD, g_res)
    print("phylum summarized gather: ", phy_sum[0])
    assert len(phy_sum) == 1
    assert phy_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),LineagePair(rank='phylum', name='b'))
    assert phy_sum[0].fraction == 0.7
    # class
    cl_sum, _ = summarize_gather_at("class", taxD, g_res)
    assert len(cl_sum) == 2
    print("class summarized gather: ", cl_sum)
    assert cl_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),
                                 LineagePair(rank='phylum', name='b'),
                                 LineagePair(rank='class', name='c'))
    assert cl_sum[0].fraction == 0.6
    assert cl_sum[1].rank == 'class'
    assert cl_sum[1].lineage == (LineagePair(rank='superkingdom', name='a'),
                                 LineagePair(rank='phylum', name='b'),
                                 LineagePair(rank='class', name='d'))
    assert cl_sum[1].fraction == 0.1


def test_summarize_gather_at_100percent_match():
    """test 100% gather match (f_unique_weighted == 1)"""
    # make mini gather_results
    gA = ["queryA", "gA","0.5","1.0", "queryA_md5", "queryA.sig"]
    gB = ["queryA", "gB","0.3","0.0", "queryA_md5", "queryA.sig"]
    g_res = make_mini_gather_results([gA,gB])

    # make mini taxonomy
    gA_tax = ("gA", "a;b;c")
    gB_tax = ("gB", "a;b;d")
    taxD = make_mini_taxonomy([gA_tax,gB_tax])

    # run summarize_gather_at and check results!
    sk_sum, _ = summarize_gather_at("superkingdom", taxD, g_res)
    # superkingdom
    assert len(sk_sum) == 1
    print("superkingdom summarized gather: ", sk_sum[0])
    assert sk_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),)
    assert sk_sum[0].fraction == 1.0


def test_summarize_gather_at_over100percent_f_unique_weighted():
    """gather matches that add up to >100% f_unique_weighted"""
    ## should we make this fail?
    # make mini gather_results
    gA = ["queryA", "gA","0.5","0.5", "queryA_md5", "queryA.sig"]
    gB = ["queryA", "gB","0.3","0.6", "queryA_md5", "queryA.sig"]
    g_res = make_mini_gather_results([gA,gB])

    # make mini taxonomy
    gA_tax = ("gA", "a;b;c")
    gB_tax = ("gB", "a;b;d")
    taxD = make_mini_taxonomy([gA_tax,gB_tax])

    # run summarize_gather_at and check results!
    sk_sum, _ = summarize_gather_at("superkingdom", taxD, g_res)
    # superkingdom
    assert len(sk_sum) == 1
    print("superkingdom summarized gather: ", sk_sum[0])
    assert sk_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),)
    assert sk_sum[0].fraction == 1.1
    # phylum
    phy_sum, _ = summarize_gather_at("phylum", taxD, g_res)
    print("phylum summarized gather: ", phy_sum[0])
    assert len(phy_sum) == 1
    assert phy_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),LineagePair(rank='phylum', name='b'))
    assert phy_sum[0].fraction == 1.1
    # class
    cl_sum, _ = summarize_gather_at("class", taxD, g_res)
    assert len(cl_sum) == 2
    print("class summarized gather: ", cl_sum)
    assert cl_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),
                                 LineagePair(rank='phylum', name='b'),
                                 LineagePair(rank='class', name='d'))
    assert cl_sum[0].fraction == 0.6
    assert cl_sum[1].rank == 'class'
    assert cl_sum[1].lineage == (LineagePair(rank='superkingdom', name='a'),
                                 LineagePair(rank='phylum', name='b'),
                                 LineagePair(rank='class', name='c'))
    assert cl_sum[1].fraction == 0.5


def test_summarize_gather_at_missing_ignore():
    """test two matches, equal f_unique_weighted"""
    # make gather results
    gA = ["queryA", "gA","0.5","0.5", "queryA_md5", "queryA.sig"]
    gB = ["queryA", "gB","0.3","0.5", "queryA_md5", "queryA.sig"]
    g_res = make_mini_gather_results([gA,gB])

    # make mini taxonomy
    gA_tax = ("gA", "a;b;c")
    taxD = make_mini_taxonomy([gA_tax])

    # run summarize_gather_at and check results!
    sk_sum, _ = summarize_gather_at("superkingdom", taxD, g_res, skip_idents=['gB'])
    # superkingdom
    assert len(sk_sum) == 1
    print("superkingdom summarized gather: ", sk_sum[0])
    assert sk_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),)
    assert sk_sum[0].fraction == 0.5

    # phylum
    phy_sum, _ = summarize_gather_at("phylum", taxD, g_res, skip_idents=['gB'])
    print("phylum summarized gather: ", phy_sum[0])
    assert len(phy_sum) == 1
    assert phy_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),LineagePair(rank='phylum', name='b'))
    assert phy_sum[0].fraction == 0.5
    # class
    cl_sum, _ = summarize_gather_at("class", taxD, g_res, skip_idents=['gB'])
    assert len(cl_sum) == 1
    print("class summarized gather: ", cl_sum)
    assert cl_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),
                                 LineagePair(rank='phylum', name='b'),
                                 LineagePair(rank='class', name='c'))
    assert cl_sum[0].fraction == 0.5


def test_summarize_gather_at_missing_fail():
    """test two matches, equal f_unique_weighted"""
    # make gather results
    gA = ["queryA", "gA","0.5","0.5", "queryA_md5", "queryA.sig"]
    gB = ["queryA", "gB","0.3","0.5", "queryA_md5", "queryA.sig"]
    g_res = make_mini_gather_results([gA,gB])

    # make mini taxonomy
    gA_tax = ("gA", "a;b;c")
    taxD = make_mini_taxonomy([gA_tax])

    # run summarize_gather_at and check results!
    with pytest.raises(ValueError) as exc:
        sk_sum, _ = summarize_gather_at("superkingdom", taxD, g_res)
        assert exc.value == "ident gB is not in the taxonomy database."


def test_summarize_gather_at_best_only_0():
    """test two matches, diff f_unique_weighted"""
    # make mini gather_results
    gA = ["queryA", "gA","0.5","0.6", "queryA_md5", "queryA.sig"]
    gB = ["queryA", "gB","0.3","0.1", "queryA_md5", "queryA.sig"]
    g_res = make_mini_gather_results([gA,gB])

    # make mini taxonomy
    gA_tax = ("gA", "a;b;c")
    gB_tax = ("gB", "a;b;d")
    taxD = make_mini_taxonomy([gA_tax,gB_tax])
    # run summarize_gather_at and check results!
    sk_sum, _ = summarize_gather_at("superkingdom", taxD, g_res, best_only=True)
    # superkingdom
    assert len(sk_sum) == 1
    print("superkingdom summarized gather: ", sk_sum[0])
    assert sk_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),)
    assert sk_sum[0].fraction == 0.7

    # phylum
    phy_sum, _ = summarize_gather_at("phylum", taxD, g_res, best_only=True)
    print("phylum summarized gather: ", phy_sum[0])
    assert len(phy_sum) == 1
    assert phy_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),LineagePair(rank='phylum', name='b'))
    assert phy_sum[0].fraction == 0.7
    # class
    cl_sum, _ = summarize_gather_at("class", taxD, g_res, best_only=True)
    assert len(cl_sum) == 1
    print("class summarized gather: ", cl_sum)
    assert cl_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),
                                 LineagePair(rank='phylum', name='b'),
                                 LineagePair(rank='class', name='c'))
    assert cl_sum[0].fraction == 0.6


def test_summarize_gather_at_best_only_equal_choose_first():
    """test two matches, equal f_unique_weighted. best_only chooses first"""
    # make mini gather_results
    gA = ["queryA", "gA","0.5","0.5", "queryA_md5", "queryA.sig"]
    gB = ["queryA", "gB","0.3","0.5", "queryA_md5", "queryA.sig"]
    g_res = make_mini_gather_results([gA,gB])

    # make mini taxonomy
    gA_tax = ("gA", "a;b;c")
    gB_tax = ("gB", "a;b;d")
    taxD = make_mini_taxonomy([gA_tax,gB_tax])

    # run summarize_gather_at and check results!
    # class
    cl_sum, _ = summarize_gather_at("class", taxD, g_res, best_only=True)
    assert len(cl_sum) == 1
    print("class summarized gather: ", cl_sum)
    assert cl_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),
                                 LineagePair(rank='phylum', name='b'),
                                 LineagePair(rank='class', name='c'))
    assert cl_sum[0].fraction == 0.5


def test_write_summary_csv(runtmp):
    """test summary csv write function"""

    sum_gather = {'superkingdom': [SummarizedGatherResult(query_name='queryA', rank='superkingdom', fraction=1.0,
                                                          query_md5='queryA_md5', query_filename='queryA.sig',
                                                          lineage=(LineagePair(rank='superkingdom', name='a'),))],
                  'phylum':  [SummarizedGatherResult(query_name='queryA', rank='phylum', fraction=1.0,
                                                     query_md5='queryA_md5', query_filename='queryA.sig',
                                                     lineage=(LineagePair(rank='superkingdom', name='a'),
                                                              LineagePair(rank='phylum', name='b')))]}

    outs= runtmp.output("outsum.csv")
    with open(outs, 'w') as out_fp:
        write_summary(sum_gather, out_fp)

    sr = [x.rstrip().split(',') for x in open(outs, 'r')]
    print("gather_summary_results_from_file: \n", sr)
    assert ['query_name', 'rank', 'fraction', 'lineage', 'query_md5', 'query_filename'] == sr[0]
    assert ['queryA', 'superkingdom', '1.000', 'a', 'queryA_md5', 'queryA.sig'] == sr[1]
    assert ['queryA', 'phylum', '1.000', 'a;b', 'queryA_md5', 'queryA.sig'] == sr[2]


def test_write_classification(runtmp):
    """test classification csv write function"""
    classif = ClassificationResult('queryA', 'match', 'phylum', 1.0,
                                    (LineagePair(rank='superkingdom', name='a'),
                                     LineagePair(rank='phylum', name='b')),
                                     'queryA_md5', 'queryA.sig')

    classification = {'phylum': [classif]}

    outs= runtmp.output("outsum.csv")
    with open(outs, 'w') as out_fp:
        write_classifications(classification, out_fp)

    sr = [x.rstrip().split(',') for x in open(outs, 'r')]
    print("gather_classification_results_from_file: \n", sr)
    assert ['query_name', 'status', 'rank', 'fraction', 'lineage', 'query_md5', 'query_filename'] == sr[0]
    assert ['queryA', 'match', 'phylum', '1.000', 'a;b', 'queryA_md5', 'queryA.sig'] == sr[1]


def test_make_krona_header_0():
    hd = make_krona_header("species")
    print("header: ", hd)
    assert hd == ("fraction", "superkingdom", "phylum", "class", "order", "family", "genus", "species")


def test_make_krona_header_1():
    hd = make_krona_header("order")
    print("header: ", hd)
    assert hd == ("fraction", "superkingdom", "phylum", "class", "order")


def test_make_krona_header_strain():
    hd = make_krona_header("strain", include_strain=True)
    print("header: ", hd)
    assert hd == ("fraction", "superkingdom", "phylum", "class", "order", "family", "genus", "species", "strain")


def test_make_krona_header_fail():
    with pytest.raises(ValueError) as exc:
        make_krona_header("strain")
        assert str(exc.value) == "Rank strain not present in available ranks"


def test_aggregate_by_lineage_at_rank_by_query():
    """test two queries, aggregate lineage at rank for each"""
    # make gather results
    gA = ["queryA","gA","0.5","0.5", "queryA_md5", "queryA.sig"]
    gB = ["queryA","gB","0.3","0.4", "queryA_md5", "queryA.sig"]
    gC = ["queryB","gB","0.3","0.3", "queryB_md5", "queryB.sig"]
    g_res = make_mini_gather_results([gA,gB,gC])

    # make mini taxonomy
    gA_tax = ("gA", "a;b")
    gB_tax = ("gB", "a;c")
    taxD = make_mini_taxonomy([gA_tax,gB_tax])

    # aggregate by lineage at rank
    sk_sum, _ = summarize_gather_at("superkingdom", taxD, g_res)
    print("superkingdom summarized gather results:", sk_sum)
    assert len(sk_sum) ==2
    assert sk_sum[0].query_name == "queryA"
    assert sk_sum[0].lineage == (LineagePair(rank='superkingdom', name='a'),)
    assert sk_sum[0].fraction == 0.9
    assert sk_sum[1].query_name == "queryB"
    assert sk_sum[1].lineage == (LineagePair(rank='superkingdom', name='a'),)
    assert sk_sum[1].fraction == 0.3
    sk_lin_sum, query_names, num_queries = aggregate_by_lineage_at_rank(sk_sum, by_query=True)
    print("superkingdom lineage summary:", sk_lin_sum, '\n')
    assert sk_lin_sum == {(LineagePair(rank='superkingdom', name='a'),): {'queryA': 0.9, 'queryB': 0.3}}
    assert num_queries == 2
    assert query_names == ['queryA', 'queryB']

    phy_sum, _ = summarize_gather_at("phylum", taxD, g_res)
    print("phylum summary:", phy_sum, ']\n')
    phy_lin_sum, query_names, num_queries = aggregate_by_lineage_at_rank(phy_sum, by_query=True)
    print("phylum lineage summary:", phy_lin_sum, '\n')
    assert phy_lin_sum ==  {(LineagePair(rank='superkingdom', name='a'), LineagePair(rank='phylum', name='b')): {'queryA': 0.5},
                            (LineagePair(rank='superkingdom', name='a'), LineagePair(rank='phylum', name='c')): {'queryA': 0.4, 'queryB': 0.3}}
    assert num_queries == 2
    assert query_names == ['queryA', 'queryB']


def test_format_for_krona_0():
    """test two matches, equal f_unique_weighted"""
    # make gather results
    gA = ["queryA", "gA","0.5","0.5", "queryA_md5", "queryA.sig"]
    gB = ["queryA", "gB","0.3","0.5", "queryA_md5", "queryA.sig"]
    g_res = make_mini_gather_results([gA,gB])

    # make mini taxonomy
    gA_tax = ("gA", "a;b;c")
    gB_tax = ("gB", "a;b;d")
    taxD = make_mini_taxonomy([gA_tax,gB_tax])

    # check krona format and check results!
    sk_sum, _ = summarize_gather_at("superkingdom", taxD, g_res)
    print("superkingdom summarized gather results:", sk_sum)
    krona_res = format_for_krona("superkingdom", {"superkingdom": sk_sum})
    print("krona_res: ", krona_res)
    assert krona_res == [(1.0, 'a')]

    phy_sum, _ = summarize_gather_at("phylum", taxD, g_res)
    krona_res = format_for_krona("phylum", {"phylum": phy_sum})
    print("krona_res: ", krona_res)
    assert krona_res == [(1.0, 'a', 'b')]


def test_format_for_krona_1():
    """test two matches, equal f_unique_weighted"""
    # make gather results
    gA = ["queryA", "gA","0.5","0.5", "queryA_md5", "queryA.sig"]
    gB = ["queryA", "gB","0.3","0.5", "queryA_md5", "queryA.sig"]
    g_res = make_mini_gather_results([gA,gB])

    # make mini taxonomy
    gA_tax = ("gA", "a;b;c")
    gB_tax = ("gB", "a;b;d")
    taxD = make_mini_taxonomy([gA_tax,gB_tax])

    # summarize with all ranks
    sum_res = {}
    #for rank in lca_utils.taxlist(include_strain=False):
    for rank in ['superkingdom', 'phylum', 'class']:
        sum_res[rank], _ = summarize_gather_at(rank, taxD, g_res)
    print('summarized gather: ', sum_res)
    # check krona format
    sk_krona = format_for_krona("superkingdom", sum_res)
    print("sk_krona: ", sk_krona)
    assert sk_krona == [(1.0, 'a')]
    phy_krona = format_for_krona("phylum", sum_res)
    print("phy_krona: ", phy_krona)
    assert phy_krona ==  [(1.0, 'a', 'b')]
    cl_krona = format_for_krona("class", sum_res)
    print("cl_krona: ", cl_krona)
    assert cl_krona ==  [(0.5, 'a', 'b', 'c'), (0.5, 'a', 'b', 'd')]


def test_format_for_krona_best_only():
    """test two matches, equal f_unique_weighted"""
    # make gather results
    gA = ["queryA", "gA","0.5","0.5", "queryA_md5", "queryA.sig"]
    gB = ["queryA", "gB","0.3","0.5", "queryA_md5", "queryA.sig"]
    g_res = make_mini_gather_results([gA,gB])

    # make mini taxonomy
    gA_tax = ("gA", "a;b;c")
    gB_tax = ("gB", "a;b;d")
    taxD = make_mini_taxonomy([gA_tax,gB_tax])

    # summarize with all ranks
    sum_res = {}
    #for rank in lca_utils.taxlist(include_strain=False):
    for rank in ['superkingdom', 'phylum', 'class']:
        sum_res[rank], _ = summarize_gather_at(rank, taxD, g_res, best_only=True)
    print('summarized gather: ', sum_res)
    # check krona format
    sk_krona = format_for_krona("superkingdom", sum_res)
    print("sk_krona: ", sk_krona)
    assert sk_krona == [(1.0, 'a')]
    phy_krona = format_for_krona("phylum", sum_res)
    print("phy_krona: ", phy_krona)
    assert phy_krona ==  [(1.0, 'a', 'b')]
    cl_krona = format_for_krona("class", sum_res)
    print("cl_krona: ", cl_krona)
    assert cl_krona ==  [(0.5, 'a', 'b', 'c')]


def test_write_krona(runtmp):
    """test two matches, equal f_unique_weighted"""
    class_krona_results =  [(0.5, 'a', 'b', 'c'), (0.5, 'a', 'b', 'd')]
    outk= runtmp.output("outkrona.tsv")
    with open(outk, 'w') as out_fp:
        write_krona("class", class_krona_results, out_fp)

    kr = [x.strip().split('\t') for x in open(outk, 'r')]
    print("krona_results_from_file: \n", kr)
    assert kr[0] == ["fraction", "superkingdom", "phylum", "class"]
    assert kr[1] == ["0.5", "a", "b", "c"]
    assert kr[2] == ["0.5", "a", "b", "d"]


def test_combine_sumgather_csvs_by_lineage(runtmp):
    # some summarized gather dicts
    sum_gather1 = {'superkingdom': [SummarizedGatherResult(query_name='queryA', rank='superkingdom', fraction=0.5,
                                                          query_md5='queryA_md5', query_filename='queryA.sig',
                                                          lineage=(LineagePair(rank='superkingdom', name='a'),))],
                  'phylum':  [SummarizedGatherResult(query_name='queryA', rank='phylum', fraction=0.5,
                                                     query_md5='queryA_md5', query_filename='queryA.sig',
                                                     lineage=(LineagePair(rank='superkingdom', name='a'),
                                                              LineagePair(rank='phylum', name='b')))]}
    sum_gather2 = {'superkingdom': [SummarizedGatherResult(query_name='queryB', rank='superkingdom', fraction=0.7,
                                                          query_md5='queryB_md5', query_filename='queryB.sig',
                                                          lineage=(LineagePair(rank='superkingdom', name='a'),))],
                  'phylum':  [SummarizedGatherResult(query_name='queryB', rank='phylum', fraction=0.7,
                                                     query_md5='queryB_md5', query_filename='queryB.sig',
                                                     lineage=(LineagePair(rank='superkingdom', name='a'),
                                                              LineagePair(rank='phylum', name='c')))]}

    # write summarized gather results csvs
    sg1= runtmp.output("sample1.csv")
    with open(sg1, 'w') as out_fp:
        write_summary(sum_gather1, out_fp)

    sg2= runtmp.output("sample2.csv")
    with open(sg2, 'w') as out_fp:
        write_summary(sum_gather2, out_fp)

    # test combine_summarized_gather_csvs_by_lineage_at_rank
    linD, query_names = combine_sumgather_csvs_by_lineage([sg1,sg2], rank="phylum")
    print("lineage_dict", linD)
    assert linD == {'a;b': {'queryA': '0.500'}, 'a;c': {'queryB': '0.700'}}
    assert query_names == ['queryA', 'queryB']
    linD, query_names = combine_sumgather_csvs_by_lineage([sg1,sg2], rank="superkingdom")
    print("lineage dict: \n", linD)
    assert linD, query_names == {'a': {'queryA': '0.500', 'queryB': '0.700'}}
    assert query_names == ['queryA', 'queryB']


def test_write_lineage_sample_frac(runtmp):
    outfrac = runtmp.output('outfrac.csv')
    sample_names = ['sample1', 'sample2']
    sk_linD = {'a': {'sample1': '0.500' ,'sample2': '0.700'}}
    with open(outfrac, 'w') as out_fp:
        write_lineage_sample_frac(sample_names, sk_linD, out_fp)

    frac_lines = [x.strip().split('\t') for x in open(outfrac, 'r')]
    print("csv_lines: ", frac_lines)
    assert frac_lines == [['lineage', 'sample1', 'sample2'], ['a', '0.500', '0.700']]

    phy_linD = {'a;b': {'sample1': '0.500'}, 'a;c': {'sample2': '0.700'}}
    with open(outfrac, 'w') as out_fp:
        write_lineage_sample_frac(sample_names, phy_linD, out_fp)

    frac_lines = [x.strip().split('\t') for x in open(outfrac, 'r')]
    print("csv_lines: ", frac_lines)
    assert frac_lines == [['lineage', 'sample1', 'sample2'], ['a;b', '0.500', '0'],  ['a;c', '0', '0.700']]


def test_write_lineage_sample_frac_format_lineage(runtmp):
    outfrac = runtmp.output('outfrac.csv')
    sample_names = ['sample1', 'sample2']
    sk_lineage = lca_utils.make_lineage('a')
    print(sk_lineage)
    sk_linD = {sk_lineage: {'sample1': '0.500' ,'sample2': '0.700'}}
    with open(outfrac, 'w') as out_fp:
        write_lineage_sample_frac(sample_names, sk_linD, out_fp, format_lineage=True)

    frac_lines = [x.strip().split('\t') for x in open(outfrac, 'r')]
    print("csv_lines: ", frac_lines)
    assert frac_lines == [['lineage', 'sample1', 'sample2'], ['a', '0.500', '0.700']]

    phy_lineage = lca_utils.make_lineage('a;b')
    print(phy_lineage)
    phy2_lineage = lca_utils.make_lineage('a;c')
    print(phy2_lineage)
    phy_linD = {phy_lineage: {'sample1': '0.500'}, phy2_lineage: {'sample2': '0.700'}}
    with open(outfrac, 'w') as out_fp:
        write_lineage_sample_frac(sample_names, phy_linD, out_fp, format_lineage=True)

    frac_lines = [x.strip().split('\t') for x in open(outfrac, 'r')]
    print("csv_lines: ", frac_lines)
    assert frac_lines == [['lineage', 'sample1', 'sample2'], ['a;b', '0.500', '0'],  ['a;c', '0', '0.700']]


def test_combine_sumgather_csvs_by_lineage_improper_rank(runtmp):
    # some summarized gather dicts
    sum_gather1 = {'superkingdom': [SummarizedGatherResult(query_name='queryA', rank='superkingdom', fraction=0.5,
                                                          query_md5='queryA_md5', query_filename='queryA.sig',
                                                          lineage=(LineagePair(rank='superkingdom', name='a'),))],
                  'phylum':  [SummarizedGatherResult(query_name='queryA', rank='phylum', fraction=0.5,
                                                     query_md5='queryA_md5', query_filename='queryA.sig',
                                                     lineage=(LineagePair(rank='superkingdom', name='a'),
                                                              LineagePair(rank='phylum', name='b')))]}
    sum_gather2 = {'superkingdom': [SummarizedGatherResult(query_name='queryB', rank='superkingdom', fraction=0.7,
                                                          query_md5='queryB_md5', query_filename='queryB.sig',
                                                          lineage=(LineagePair(rank='superkingdom', name='a'),))],
                  'phylum':  [SummarizedGatherResult(query_name='queryB', rank='phylum', fraction=0.7,
                                                     query_md5='queryB_md5', query_filename='queryB.sig',
                                                     lineage=(LineagePair(rank='superkingdom', name='a'),
                                                              LineagePair(rank='phylum', name='c')))]}

    # write summarized gather results csvs
    sg1= runtmp.output("sample1.csv")
    with open(sg1, 'w') as out_fp:
        write_summary(sum_gather1, out_fp)

    sg2= runtmp.output("sample2.csv")
    with open(sg2, 'w') as out_fp:
        write_summary(sum_gather2, out_fp)

    # test combine_summarized_gather_csvs_by_lineage_at_rank
    with pytest.raises(ValueError) as exc:
        linD, sample_names = combine_sumgather_csvs_by_lineage([sg1,sg2], rank="strain")
        print("ValueError: ", exc.value)
        assert exc.value == "Rank strain not available."