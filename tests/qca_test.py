import json
import requests
from nose import SkipTest
from tests.util import ekb_kstring_from_text, ekb_from_text, get_request
from tests.integration import _IntegrationTest
from indra.statements import stmts_from_json, Gef
from kqml import KQMLList
from bioagents.qca import QCA, QCA_Module
from bioagents.qca.qca import PathScoring


def _get_qca_content(task, source, target):
    """Get the KQMLList content to be sent to the QCA for given task.

    Paramters
    ---------
    source, target : str
        The strings representing the proteins for source and target,
        respectively, for example 'BRAF'.

    Returns
    -------
    content : KQMLList
        The KQML content to be sent to the QCA module as part of the request.
    """
    content = KQMLList(task)
    content.set('source', ekb_kstring_from_text(source))
    content.set('target', ekb_kstring_from_text(target))
    return content


class TestSosKras(_IntegrationTest):
    def __init__(self, *args):
        super(TestSosKras, self).__init__(QCA_Module)

    def create_message(self):
        content = _get_qca_content('FIND-QCA-PATH', 'SOS1', 'KRAS')
        msg = get_request(content)
        return msg, content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS'
        paths = output.get('paths')
        assert len(paths) == 1
        path = paths[0].string_value()
        path_json = json.loads(path)
        stmts = stmts_from_json(path_json)
        assert len(stmts) == 1
        assert isinstance(stmts[0], Gef)
        assert stmts[0].ras.name == 'KRAS'
        assert stmts[0].gef.name == 'SOS1'


def test_find_qca_path():
    content = _get_qca_content('FIND-QCA-PATH', 'MAP2K1', 'BRAF')
    qca_mod = QCA_Module(testing=True)
    resp = qca_mod.respond_find_qca_path(content)
    assert resp is not None, "No response received."
    assert resp.head() is "SUCCESS", \
        "QCA failed task for reason: %s" % resp.gets('reason')
    assert resp.get('paths') is not None, "Did not find paths."
    return


def test_has_qca_path():
    content = _get_qca_content('HAS-QCA-PATH', 'MAP2K1', 'BRAF')
    qca_mod = QCA_Module(testing=True)
    resp = qca_mod.respond_has_qca_path(content)
    assert resp is not None, "No response received."
    assert resp.head() is "SUCCESS", \
        "QCA failed task for reason: %s" % resp.gets('reason')
    assert resp.get('haspath') == 'TRUE', "Did not find path."
    return


class ProvenanceTest(_IntegrationTest):
    """Test whether we are creating provenance for sbgnviz.

    At the moment this is a very simple test which only determines that there
    was some provenance sent, and checks nothing about the quality of the
    provenance.
    """

    def __init__(self, *args):
        super(ProvenanceTest, self).__init__(QCA_Module)

    def create_message(self):
        content = _get_qca_content('FIND-QCA-PATH', 'MAP2K1', 'BRAF')
        msg = get_request(content)
        return msg, content

    def check_response_to_message(self, output):
        # If there wasn't a succes, we won't get provenance.
        if not output.head() == 'SUCCESS':
            raise SkipTest('QCA could not find path, so there won\'t be '
                           'any provenance.')
        output_log = self.get_output_log()
        assert any([('tell' in line and 'add-provenance' in line)
                    for line in output_log])
        return


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
        'http://general.bigmech.ndexbio.org:5603/directedpath/query'

    # Assemble REST url
    uuid_prior = "50e3dff7-133e-11e6-a039-06603eb7f303"
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
