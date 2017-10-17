import json
from kqml import KQMLList, KQMLPerformative
from indra.statements import *
from tests.util import *
from tests.integration import _IntegrationTest, _FailureTest
from bioagents.mra import MRA, MRA_Module
from bioagents.mra.mra_module import ekb_from_agent, get_target

# ################
# MRA unit tests
# ################
def test_agent_to_ekb():
    egfr = Agent('EGFR', db_refs = {'HGNC': '3236', 'TEXT': 'EGFR'})
    term = ekb_from_agent(egfr)
    egfr_out = get_target(term)
    assert(isinstance(egfr_out, Agent))
    assert(egfr_out.name == 'EGFR')


def test_build_model_from_ekb():
    m = MRA()
    ekb = ekb_from_text('MAP2K1 phosphorylates MAPK1.')
    res = m.build_model_from_ekb(ekb)
    assert(res.get('model'))
    assert(res.get('model_id') == 1)
    assert(res.get('model_exec'))
    assert(len(m.models[1]) == 1)
    assert(isinstance(m.models[1][0], Phosphorylation))
    assert(m.models[1][0].enz.name == 'MAP2K1')


def test_expand_model_from_ekb():
    m = MRA()
    ekb = ekb_from_text('MAP2K1 phosphorylates MAPK1.')
    res = m.build_model_from_ekb(ekb)
    model_id = res.get('model_id')
    assert(res.get('model'))
    assert(res.get('model_id') == 1)
    assert(len(m.models[1]) == 1)
    ekb = ekb_from_text('MAP2K2 phosphorylates MAPK1.')
    res = m.expand_model_from_ekb(ekb, model_id)
    assert(res.get('model'))
    assert(res.get('model_id') == 2)
    assert(len(m.models[2]) == 2)


def test_get_upstream():
    m = MRA()
    egfr = Agent('EGFR', db_refs = {'HGNC': '3236', 'TEXT': 'EGFR'})
    kras = Agent('KRAS', db_refs = {'HGNC': '6407', 'TEXT': 'KRAS'})
    stmts = [Activation(egfr, kras)]
    model_id = m.new_model(stmts)
    upstream = m.get_upstream(kras, model_id)
    assert(len(upstream) == 1)
    assert(upstream[0].name == 'EGFR')


def test_has_mechanism():
    m = MRA()
    ekb = ekb_from_text('BRAF binds MEK')
    m.build_model_from_ekb(ekb)
    has_mechanism = m.has_mechanism(ekb, 1)
    assert(has_mechanism)


def test_transformations():
    m = MRA()
    stmts1 = [Phosphorylation(Agent('A'), Agent('B'))]
    m.new_model(stmts1)
    assert(len(m.transformations) == 1)
    tr = m.transformations[0]
    assert(tr[0] == 'add_stmts')
    assert(tr[1] == stmts1)
    assert(tr[2] is None)
    assert(tr[3] == 1)
    stmts2 = [Phosphorylation(Agent('C'), Agent('D'))]
    m.extend_model(stmts2, 1)
    assert(len(m.transformations) == 2)
    tr = m.transformations[1]
    assert(tr[0] == 'add_stmts')
    assert(tr[1] == stmts2)
    assert(tr[2] == 1)
    assert(tr[3] == 2)


def test_model_undo():
    m = MRA()
    stmts1 = [Phosphorylation(Agent('A'), Agent('B'))]
    m.new_model(stmts1)
    res = m.model_undo()
    action = res.get('action')
    assert action is not None
    assert action.get('action') == 'remove_stmts'
    assert action.get('statements') == stmts1


# #####################
# MRA_Module unit tests
# #####################

def test_respond_build_model_from_json():
    mm = MRA_Module(testing=True)
    st = Phosphorylation(Agent('MEK'), Agent('ERK'))
    msg = KQMLList('BUILD-MODEL')
    msg.sets('description', json.dumps(stmts_to_json([st])))
    msg.sets('format', 'indra_json')
    reply = mm.respond_build_model(msg)
    assert(reply.get('model'))
    assert(reply.get('model-id') == '1')


def test_respond_expand_model_from_json():
    mm = MRA_Module(testing=True)
    st = Phosphorylation(Agent('MEK'), Agent('ERK'))
    msg = KQMLList('BUILD-MODEL')
    msg.sets('description', json.dumps(stmts_to_json([st])))
    msg.sets('format', 'indra_json')
    reply = mm.respond_build_model(msg)
    assert(reply.get('model'))
    assert(reply.get('model-id') == '1')
    st = Phosphorylation(Agent('RAF'), Agent('MEK'))
    msg = KQMLList('EXPAND-MODEL')
    msg.sets('description', json.dumps(stmts_to_json([st])))
    msg.sets('format', 'indra_json')
    msg.set('model-id', '1')
    reply = mm.respond_expand_model(msg)
    assert(reply.get('model'))
    assert(reply.get('model-id') == '2')


def test_respond_model_get_upstream():
    mm = MRA_Module(testing=True)
    egfr = Agent('EGFR', db_refs = {'HGNC': '3236', 'TEXT': 'EGFR'})
    kras = Agent('KRAS', db_refs = {'HGNC': '6407', 'TEXT': 'KRAS'})
    stmts = [Activation(egfr, kras)]
    model_id = mm.mra.new_model(stmts)
    kras_term = ekb_from_agent(kras)
    msg = KQMLList('MODEL-GET-UPSTREAM')
    msg.sets('target', kras_term)
    msg.set('model-id', str(model_id))
    reply = mm.respond_model_get_upstream(msg)
    ups = reply.get('upstream')
    assert(len(ups) == 1)


def test_respond_model_undo():
    mm = MRA_Module(testing=True)
    _, content = _get_build_model_request('HRAS activates RAF')
    reply = mm.respond_build_model(content)
    _, content = _get_expand_model_request('NRAS activates RAF', '1')
    expand_reply = mm.respond_expand_model(content)
    expand_stmts = expand_reply.gets('model-new')
    content = KQMLList.from_string('(MODEL-UNDO)')
    reply = mm.respond_model_undo(content)
    assert reply.gets('model-id') == '3'
    action = reply.get('action')
    assert action.head() == 'remove_stmts'
    stmts = action.get('statements')
    assert json.loads(stmts.string_value()) == json.loads(expand_stmts)


# #####################
# MRA integration tests
# #####################

def _get_build_model_request(text):
    content = KQMLList('BUILD-MODEL')
    descr = ekb_kstring_from_text(text)
    content.set('description', descr)
    return get_request(content), content


def _get_expand_model_request(text, model_id):
    content = KQMLList('EXPAND-MODEL')
    descr = ekb_kstring_from_text(text)
    content.set('description', descr)
    content.set('model-id', model_id)
    return get_request(content), content


class TestBuildModelAmbiguity(_IntegrationTest):
    def __init__(self, *args):
        super(TestBuildModelAmbiguity, self).__init__(MRA_Module)

    def create_message(self):
        return _get_build_model_request('MEK1 phosphorylates ERK2')

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        assert output.get('model') is not None
        ambiguities = output.get('ambiguities')
        assert len(ambiguities) == 1
        assert ambiguities[0].get('preferred').to_string() == \
            '(term :ont-type ONT::PROTEIN ' + \
            ':ids "HGNC::6840|NCIT::C52823|UP::Q02750" :name "MAP2K1")'
        assert ambiguities[0].get('alternative').to_string() == \
            '(term :ont-type ONT::PROTEIN-FAMILY ' + \
            ':ids "BE::MAP2K|NCIT::C105947" ' + \
            ':name "mitogen-activated protein kinase kinase")'
        assert output.get('diagram') is not None
        assert output.gets('diagram').endswith('png')


class TestBuildModelBoundCondition(_IntegrationTest):
    def __init__(self, *args):
        super(TestBuildModelBoundCondition, self).__init__(MRA_Module)

    def create_message(self):
        txt = 'KRAS bound to GTP phosphorylates BRAF on T373.'
        return _get_build_model_request(txt)

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        model = output.gets('model')
        assert model is not None
        indra_stmts_json = json.loads(model)
        assert(len(indra_stmts_json) == 1)
        stmt = stmts_from_json(indra_stmts_json)[0]
        assert(isinstance(stmt, Phosphorylation))
        assert(stmt.enz.bound_conditions[0].agent.name == 'GTP')


class TestBuildModelComplex(_IntegrationTest):
    def __init__(self, *args):
        super(TestBuildModelComplex, self).__init__(MRA_Module)

    def create_message(self):
        txt = 'The EGFR-EGF complex activates SOS1.'
        return _get_build_model_request(txt)

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        model = output.gets('model')
        assert model is not None
        indra_stmts_json = json.loads(model)
        assert(len(indra_stmts_json) == 1)
        stmt = stmts_from_json(indra_stmts_json)[0]
        assert(isinstance(stmt, Activation))
        assert(stmt.subj.bound_conditions[0].agent.name == 'EGF')



class TestModelUndo(_IntegrationTest):
    def __init__(self, *args):
        super(TestModelUndo, self).__init__(MRA_Module)
        # Start off with a model
        msg, content = _get_build_model_request('MEK1 phosphorylates ERK2')
        self.bioagent.receive_request(msg, content)

    def create_message(self):
        content = KQMLList('MODEL-UNDO')
        msg = get_request(content)
        return msg, content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '2'
        assert output.gets('model') == '[]'


class TestMissingDescriptionFailure(_FailureTest):
    def __init__(self, *args):
        super(TestMissingDescriptionFailure, self).__init__(MRA_Module)
        self.expected_reason = 'INVALID_DESCRIPTION'

    def create_message(self):
        content = KQMLList('BUILD-MODEL')
        content.sets('description', '')
        msg = get_request(content)
        return msg, content


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
