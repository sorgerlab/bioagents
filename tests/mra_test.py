from bioagents.mra import MRA
import indra.statements
from indra.trips import trips_client

def test_build_model_from_text():
    m = MRA()
    model = m.build_model_from_text('MEK1 phosphorylates ERK2.')
    assert(model is not None)
    assert(len(m.statements) == 1)
    assert(len(m.statements[0]) == 1)
    assert(isinstance(m.statements[0][0], indra.statements.Phosphorylation))
    assert(m.statements[0][0].enz.name == 'MAP2K1')
    assert(m.statements[0][0].sub.name == 'MAPK1')

def test_build_model_from_ekb():
    m = MRA()
    html = trips_client.send_query('MEK1 phosphorylates ERK2.')
    ekb_xml = trips_client.get_xml(html)
    model = m.build_model_from_ekb(ekb_xml)
    assert(model is not None)
    assert(len(m.statements[0]) == 1)
    assert(isinstance(m.statements[0][0], indra.statements.Phosphorylation))
    assert(m.statements[0][0].enz.name == 'MAP2K1')
    assert(m.statements[0][0].sub.name == 'MAPK1')

def test_replace_agent_one():
    m = MRA()
    m.build_model_from_text('BRAF binds MEK1.')
    m.replace_agent('BRAF', ['RAF1'], 1)
    assert(len(m.statements) == 1)
    assert(len(m.statements[0]) == 1)
    assert((m.statements[0][0].members[0].name == 'RAF1') or\
            (m.statements[0][0].members[1].name == 'RAF1'))

#def test_replace_agent_multiple():
#    m = MRA()
#    m.build_model_from_text('Raf phosphorylates Erk.')
#    m.replace_agent('Raf', ['BRAF', 'RAF1'])
#    assert(len(m.statements) == 2)
#    assert(m.statements[0].enz.name == 'BRAF')
#    assert(m.statements[1].enz.name == 'RAF1')

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

