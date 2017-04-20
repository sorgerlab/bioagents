from kqml import *
from indra.statements import *
from indra.trips import trips_client
from bioagents.mra import MRA, MRA_Module
from bioagents.mra.mra_module import ekb_from_agent, get_target


def test_build_model_from_ekb():
    m = MRA()
    html = trips_client.send_query('MAP2K1 phosphorylates ERK2.')
    ekb_xml = trips_client.get_xml(html)
    res = m.build_model_from_ekb(ekb_xml)
    assert(res.get('model'))
    assert(res.get('model_id') == 1)
    assert(res.get('model_exec'))
    assert(len(m.models[1]) == 1)
    assert(isinstance(m.models[1][0], Phosphorylation))
    assert(m.models[1][0].enz.name == 'MAP2K1')
    assert(m.models[1][0].sub.name == 'MAPK1')

def test_agent_to_ekb():
    egfr = Agent('EGFR', db_refs = {'HGNC': '3236', 'TEXT': 'EGFR'})
    term = ekb_from_agent(egfr)
    egfr_out = get_target(term)
    assert(isinstance(egfr_out, Agent))
    assert(egfr_out.name == 'EGFR')

def test_get_upstream():
    m = MRA()
    egfr = Agent('EGFR', db_refs = {'HGNC': '3236', 'TEXT': 'EGFR'})
    kras = Agent('KRAS', db_refs = {'HGNC': '6407', 'TEXT': 'KRAS'})
    stmts = [Activation(egfr, kras)]
    model_id = m.new_model(stmts)
    upstream = m.get_upstream(kras, model_id)
    assert(len(upstream) == 1)
    assert(upstream[0].name == 'EGFR')
    mm = MRA_Module(None, True)
    mm.mra = m
    egfr_term = ekb_from_agent(egfr)
    msg = KQMLList('MODEL-GET-UPSTREAM')
    msg.sets('target', egfr_term)
    msg.set('model-id', str(model_id))
    reply = mm.respond_model_get_upstream(msg)

'''
def test_replace_agent_one():
    m = MRA()
    m.build_model_from_text('BRAF binds MEK1.')
    m.replace_agent('BRAF', ['RAF1'], 1)
    assert(len(m.statements) == 1)
    assert(len(m.statements[0]) == 1)
    assert((m.statements[0][0].members[0].name == 'RAF1') or\
            (m.statements[0][0].members[1].name == 'RAF1'))


def test_find_family_members_name():
    m = MRA()
    family_members = m.find_family_members('Raf')
    assert(family_members is not None)
    assert(len(family_members) == 3)
    assert('BRAF' in family_members)

def test_find_family_members_id():
    m = MRA()
    family_members = m.find_family_members('', family_id='FA:03114')
    assert(family_members is not None)
    assert(len(family_members) == 3)
    assert('BRAF' in family_members)
'''

def test_has_mechanism():
    m = MRA()
    ekb = '<ekb><EVENT id="V33716"><type>ONT::BIND</type><arg1 id="V33712" role=":AGENT" /><arg2 id="V33734" role=":AFFECTED" /></EVENT><TERM id="V33712" dbid="HGNC:1097|NCIT:C51194|NCIT:C17476"><features></features><type>ONT::GENE-PROTEIN</type><name>BRAF</name></TERM><TERM id="V33734" dbid="NCIT:C52823|NCIT:C105947|NCIT:C17808|HGNC:6840|UP:Q91447|UP:Q05116"><features></features><type>ONT::GENE-PROTEIN</type><name>MEK-1</name></TERM></ekb>'
    m.build_model_from_ekb(ekb)
    has_mechanism = m.has_mechanism(ekb, 1)
    assert(has_mechanism)
