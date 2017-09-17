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


# #####################
# MRA integration tests
# #####################

def _get_build_model_request(text):
    content = KQMLList('BUILD-MODEL')
    descr = ekb_kstring_from_text(text)
    content.set('description', descr)
    return _get_request(content), content


def _get_request(content):
    msg = KQMLPerformative('REQUEST')
    msg.set('content', content)
    msg.set('reply-with', 'IO-1')
    return msg


class TestBuildModelAmbiguity(_IntegrationTest):
    def __init__(self, *args):
        super(TestBuildModelAmbiguity, self).__init__(MRA_Module)

    def get_message(self):
        return _get_build_model_request('MEK1 phosphorylates ERK2')

    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS'
        assert self.output.get('model-id') == '1'
        assert self.output.get('model') is not None
        ambiguities = self.output.get('ambiguities')
        assert len(ambiguities) == 1
        assert ambiguities[0].get('preferred').to_string() == \
            '(term :ont-type ONT::PROTEIN ' + \
            ':ids "HGNC::6840|NCIT::C52823|UP::Q02750" :name "MAP2K1")'
        assert ambiguities[0].get('alternative').to_string() == \
            '(term :ont-type ONT::PROTEIN-FAMILY ' + \
            ':ids "BE::MAP2K|NCIT::C105947" ' + \
            ':name "mitogen-activated protein kinase kinase")'
        assert self.output.get('diagram') is not None
        assert self.output.gets('diagram').endswith('png')
        return True

    def give_feedback(self):
        return None


class TestModelUndo(_IntegrationTest):
    def __init__(self, *args):
        super(TestModelUndo, self).__init__(MRA_Module)
        # Start off with a model
        msg, content = _get_build_model_request('MEK1 phosphorylates ERK2')
        self.bioagent.receive_request(msg, content)

    def get_message(self):
        content = KQMLList('MODEL-UNDO')
        msg = _get_request(content)
        return msg, content

    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS'
        assert self.output.get('model-id') == '2'
        assert self.output.gets('model') == '[]'
        return True

    def give_feedback(self):
        return None

# THIS TEST IS FAILING DUE TO THE INTERNAL_ERROR BUG, REMOVED FOR NOW
'''
class TestMissingDescriptionFailure(_FailureTest):
    def __init__(self, *args):
        super(TestMissingDescriptionFailure, self).__init__(MRA_Module)
        self.expected_reason = 'INVALID_DESCRIPTION'

    def get_message(self):
        content = KQMLList('BUILD-MODEL')
        content.sets('description', '')
        msg = _get_request(content)
        print(content)
        return msg, content
'''

def test_undo():
    mm = MRA_Module(testing=True)
    kl = KQMLList.from_string('(BUILD-MODEL :DESCRIPTION "<ekb><EVENT id=\\"V34357\\"><type>ONT::ACTIVATE</type><arg1 id=\\"V34353\\" role=\\":AGENT\\" /><arg2 id=\\"V34364\\" role=\\":AFFECTED\\" /></EVENT><TERM id=\\"V34364\\" dbid=\\"FA:03114|BE:RAF|NCIT:C51274|UP:Q06891\\"><features></features><type>ONT::GENE-PROTEIN</type><name>RAF</name><drum-terms><drum-term dbid=\\"FA:03114\\" match-score=\\"1.0\\" name=\\"RAF subfamily\\" /><drum-term dbid=\\"BE:RAF\\" match-score=\\"1.0\\" name=\\"RAF\\" /><drum-term dbid=\\"NCIT:C51274\\" match-score=\\"0.82857\\" name=\\"RAF1\\" /><drum-term dbid=\\"UP:Q06891\\" match-score=\\"0.65714\\" name=\\"Trans-acting factor D\\" /></drum-terms></TERM><TERM id=\\"V34353\\" dbid=\\"NCIT:C52545|HGNC:5173|NCIT:C16659|NCIT:C17382\\"><features></features><type>ONT::GENE-PROTEIN</type><name>HRAS</name><drum-terms><drum-term dbid=\\"NCIT:C52545\\" match-score=\\"1.0\\" name=\\"HRAS\\" /><drum-term dbid=\\"HGNC:5173\\" match-score=\\"1.0\\" name=\\"Harvey rat sarcoma viral oncogene homolog\\" /><drum-term dbid=\\"NCIT:C16659\\" match-score=\\"0.82857\\" name=\\"oncogene H-ras\\" /><drum-term dbid=\\"NCIT:C17382\\" match-score=\\"0.82857\\" name=\\"p21 H-ras protein\\" /></drum-terms></TERM></ekb>")')
    reply = mm.respond_build_model(kl)
    print(reply)
    kl = KQMLList.from_string('(EXPAND-MODEL :MODEL-ID 1 :DESCRIPTION "<ekb><EVENT id=\\"V34455\\"><type>ONT::ACTIVATE</type><arg1 id=\\"V34451\\" role=\\":AGENT\\" /><arg2 id=\\"V34462\\" role=\\":AFFECTED\\" /></EVENT><TERM id=\\"V34462\\" dbid=\\"FA:03114|BE:RAF|NCIT:C51274|UP:Q06891\\"><features></features><type>ONT::GENE-PROTEIN</type><name>RAF</name><drum-terms><drum-term dbid=\\"FA:03114\\" match-score=\\"1.0\\" name=\\"RAF subfamily\\" /><drum-term dbid=\\"BE:RAF\\" match-score=\\"1.0\\" name=\\"RAF\\" /><drum-term dbid=\\"NCIT:C51274\\" match-score=\\"0.82857\\" name=\\"RAF1\\" /><drum-term dbid=\\"UP:Q06891\\" match-score=\\"0.65714\\" name=\\"Trans-acting factor D\\" /></drum-terms></TERM><TERM id=\\"V34451\\" dbid=\\"NCIT:C52549|HGNC:7989|NCIT:C16889|NCIT:C17384\\"><features></features><type>ONT::GENE-PROTEIN</type><name>NRAS</name><drum-terms><drum-term dbid=\\"NCIT:C52549\\" match-score=\\"1.0\\" name=\\"NRAS\\" /><drum-term dbid=\\"HGNC:7989\\" match-score=\\"1.0\\" name=\\"neuroblastoma RAS viral oncogene homolog\\" /><drum-term dbid=\\"NCIT:C16889\\" match-score=\\"0.82857\\" name=\\"oncogene N-RAS\\" /><drum-term dbid=\\"NCIT:C17384\\" match-score=\\"0.82857\\" name=\\"p21 N-ras protein\\" /></drum-terms></TERM></ekb>")')
    reply = mm.respond_expand_model(kl)
    print(reply)
    kl = KQMLList.from_string('(MODEL-UNDO)')
    reply = mm.respond_model_undo(kl)
    print(reply)

def test_has_mechanism():
    m = MRA()
    ekb = ekb_from_text('BRAF binds MEK')
    m.build_model_from_ekb(ekb)
    has_mechanism = m.has_mechanism(ekb, 1)
    assert(has_mechanism)

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
