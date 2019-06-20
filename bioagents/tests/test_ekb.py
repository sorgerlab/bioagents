import os
from bioagents.ekb import agent_from_term, KQMLGraph
from kqml import KQMLList

path_here = os.path.dirname(os.path.abspath(__file__))


def _load_kqml(fname):
    fname = os.path.join(path_here, 'kqml', fname)
    with open(fname, 'r') as fh:
        kqml_string = fh.read()
    return kqml_string


def test_process_kqml():
    fname = os.path.join(path_here, 'what_drugs_target_braf.kqml')
    with open(fname, 'r') as fh:
        kqml_string = fh.read()

    G = KQMLGraph(kqml_string)
    braf_id = 'V34745'
    agent = agent_from_term(G, braf_id)
    assert agent.name == 'BRAF'
    assert 'HGNC' in agent.db_refs


def test_get_drug_agent():
    kqml_str = _load_kqml('tofacitinib.kqml')
    kqml = KQMLList.from_string(kqml_str)
    context = kqml.get('context')
    graph = KQMLGraph(context)
    agent = agent_from_term(graph, 'V34850')
    assert agent.name == 'TOFACITINIB', agent
    assert 'PUBCHEM' in agent.db_refs, agent.db_refs
