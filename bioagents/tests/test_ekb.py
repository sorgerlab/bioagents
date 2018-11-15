import os
from bioagents.ekb import ekb
from bioagents.ekb import kqml_graph


path_here = os.path.dirname(os.path.abspath(__file__))


def test_process_kqml():
    fname = os.path.join(path_here, 'what_drugs_target_braf.kqml')
    with open(fname, 'r') as fh:
        kqml_string = fh.read()

    G = kqml_graph.KQMLGraph(kqml_string)
    braf_id = 'V34745'
    agent = ekb.agent_from_term(G, braf_id)
    assert agent.name == 'BRAF'
    assert 'HGNC' in agent.db_refs
