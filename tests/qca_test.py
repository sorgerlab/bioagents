import json
import unittest
import requests
from ndex.beta.path_scoring import PathScoring
from bioagents.qca import QCA
from kqml.kqml_list import KQMLList
from tests.util import ekb_from_text
from bioagents.qca.qca_module import QCA_Module


# BELOW ARE OLD QCA TESTS

def test_improved_path_ranking():
    qca = QCA()
    sources = ["E2F1"]
    targets = ["PTEN"]
    qca_results2 = qca.find_causal_path(targets, sources)
    print(qca_results2)
    assert len(qca_results2) > 0


def test_scratch():
    source_names = ["AKT1", "AKT2", "AKT3"]
    target_names = ["CCND1"]
    results_list = []
    directed_path_query_url = \
        'http://general.bigmech.ndexbio.org/directedpath/query'

    # Assemble REST url
    uuid_prior = "84f321c6-dade-11e6-86b1-0ac135e8bacf"
    target = ",".join(target_names)
    source = ",".join(source_names)
    max_number_of_paths = 200
    url = '%s?source=%s&target=%s&uuid=%s&server=%s&pathnum=%s' % (
        directed_path_query_url,
        source,
        target,
        uuid_prior,
        'www.ndexbio.org',
        str(max_number_of_paths)
        )

    r = requests.post(url)
    result_json = json.loads(r.content)

    edge_results = result_json.get("data").get("forward_english")
    path_scoring = PathScoring()

    A_all_scores = []

    for i, edge in enumerate(edge_results):
        print len(edge)
        top_edge = None
        for ranked_edges in path_scoring.cx_edges_to_tuples(edge, "A"):
            if top_edge is None:
                top_edge = ranked_edges
            else:
                if ranked_edges[1] < top_edge[1]:
                    top_edge = ranked_edges

        A_all_scores.append(("A" + str(i), top_edge[1]))

    print(A_all_scores)
    race_results = path_scoring.calculate_average_position(A_all_scores, [])

    print(race_results)
    print(results_list)


def test_find_qca_path():
    content = KQMLList('FIND-QCA-PATH')
    content.sets('target', ekb_from_text('MAP2K1'))
    content.sets('source', ekb_from_text('BRAF'))
    qca_mod = QCA_Module(testing=True)
    resp = qca_mod.respond_find_qca_path(content)
    assert resp is not None, "No response received."
    assert resp.head() is "SUCCESS", \
        "QCA failed task for reason: %s" % resp.gets('reason')
    assert resp.get('paths') is not None, "Did not find paths."
    return


if __name__ == '__main__':
    unittest.main()
