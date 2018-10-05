import json
import unittest
import xml.etree.ElementTree as ET
from kqml.kqml_list import KQMLList
import indra.statements as sts
from bioagents.tests.util import ekb_from_text, ekb_kstring_from_text, \
        get_request, stmts_json_from_text
from bioagents.tests.integration import _IntegrationTest, _FailureTest
from bioagents.mra.mra import MRA, make_influence_map, make_contact_map
from bioagents.mra.mra_module import MRA_Module, ekb_from_agent, get_target, \
    _get_matching_stmts, CAN_CHECK_STATEMENTS
from nose.plugins.skip import SkipTest


# ################
# MRA unit tests
# ################
def test_agent_to_ekb():
    egfr = sts.Agent('EGFR', db_refs={'HGNC': '3236', 'TEXT': 'EGFR'})
    term = ekb_from_agent(egfr)
    egfr_out = get_target(term)
    assert(isinstance(egfr_out, sts.Agent))
    assert(egfr_out.name == 'EGFR')


def test_build_model_from_ekb():
    m = MRA()
    ekb = ekb_from_text('MAP2K1 phosphorylates MAPK1.')
    res = m.build_model_from_ekb(ekb)
    assert(res.get('model'))
    assert(res.get('model_id') == 1)
    assert(res.get('model_exec'))
    assert(len(m.models[1]) == 1)
    assert(isinstance(m.models[1][0], sts.Phosphorylation))
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
    egfr = sts.Agent('EGFR', db_refs={'HGNC': '3236', 'TEXT': 'EGFR'})
    kras = sts.Agent('KRAS', db_refs={'HGNC': '6407', 'TEXT': 'KRAS'})
    stmts = [sts.Activation(egfr, kras)]
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
    stmts1 = [sts.Phosphorylation(sts.Agent('A'), sts.Agent('B'))]
    m.new_model(stmts1)
    assert(len(m.transformations) == 1)
    tr = m.transformations[0]
    assert(tr[0] == 'add_stmts')
    assert(tr[1] == stmts1)
    assert(tr[2] is None)
    assert(tr[3] == 1)
    stmts2 = [sts.Phosphorylation(sts.Agent('C'), sts.Agent('D'))]
    m.extend_model(stmts2, 1)
    assert(len(m.transformations) == 2)
    tr = m.transformations[1]
    assert(tr[0] == 'add_stmts')
    assert(tr[1] == stmts2)
    assert(tr[2] == 1)
    assert(tr[3] == 2)


def test_model_undo():
    m = MRA()
    stmts1 = [sts.Phosphorylation(sts.Agent('A'), sts.Agent('B'))]
    m.new_model(stmts1)
    res = m.model_undo()
    action = res.get('action')
    assert action is not None
    assert action.get('action') == 'remove_stmts'
    assert action.get('statements') == stmts1


def test_sbgn():
    m = MRA()
    ekb = ekb_from_text('KRAS activates BRAF.')
    res = m.build_model_from_ekb(ekb)
    ekb = ekb_from_text('NRAS activates BRAF.')
    res = m.expand_model_from_ekb(ekb, 1)
    sbgn = res['diagrams']['sbgn']
    tree = ET.fromstring(sbgn)
    glyphs = tree.findall('s:map/s:glyph',
                          namespaces={'s': 'http://sbgn.org/libsbgn/0.3'})
    assert len(glyphs) == 6
    res = m.model_undo()
    sbgn = res['diagrams']['sbgn']
    tree = ET.fromstring(sbgn)
    glyphs = tree.findall('s:map/s:glyph',
                          namespaces={'s': 'http://sbgn.org/libsbgn/0.3'})
    assert len(glyphs) == 4


def test_make_diagrams():
    m = MRA()
    ekb = ekb_from_text('KRAS activates BRAF. Active BRAF binds MEK.')
    res = m.build_model_from_ekb(ekb)
    diagrams = res['diagrams']
    assert diagrams['reactionnetwork']
    assert diagrams['reactionnetwork'].endswith('.png')
    assert diagrams['contactmap']
    assert diagrams['contactmap'].endswith('.png')
    assert diagrams['influencemap']
    assert diagrams['influencemap'].endswith('.png')


def test_make_im():
    m = MRA()
    ekb = ekb_from_text('KRAS activates BRAF. Active BRAF binds MEK.')
    res = m.build_model_from_ekb(ekb)
    pysb_model = res['model_exec']
    im = make_influence_map(pysb_model)
    assert len(list(im.nodes())) == 3
    assert len(list(im.edges())) == 3


def test_make_cm():
    m = MRA()
    ekb = ekb_from_text('MEK binds MAPK1. MEK binds MAPK3.')
    res = m.build_model_from_ekb(ekb)
    pysb_model = res['model_exec']
    cm = make_contact_map(pysb_model)
    assert len(list(cm.nodes())) == 3
    assert len(list(cm.edges())) == 2


# #####################
# MRA_Module unit tests
# #####################

def test_respond_build_model_from_json():
    mm = MRA_Module(testing=True)
    st = sts.Phosphorylation(sts.Agent('MEK'), sts.Agent('ERK'))
    msg = KQMLList('BUILD-MODEL')
    msg.sets('description', json.dumps(sts.stmts_to_json([st])))
    msg.sets('format', 'indra_json')
    reply = mm.respond_build_model(msg)
    assert(reply.get('model'))
    assert(reply.get('model-id') == '1')


def test_respond_expand_model_from_json():
    mm = MRA_Module(testing=True)
    st = stmts_json_from_text('MEK phosphorylates ERK')
    msg = KQMLList('BUILD-MODEL')
    msg.sets('description', json.dumps(st))
    msg.sets('format', 'indra_json')
    reply = mm.respond_build_model(msg)
    assert(reply.get('model'))
    assert(reply.get('model-id') == '1')

    st = stmts_json_from_text('Active BRAF inhibits MEK.')
    msg = KQMLList('EXPAND-MODEL')
    msg.sets('description', json.dumps(st))
    msg.sets('format', 'indra_json')
    msg.set('model-id', '1')
    reply = mm.respond_expand_model(msg)
    assert(reply.get('model'))
    assert(reply.get('model-id') == '2')


def test_respond_model_get_upstream():
    mm = MRA_Module(testing=True)
    egfr = sts.Agent('EGFR', db_refs={'HGNC': '3236', 'TEXT': 'EGFR'})
    kras = sts.Agent('KRAS', db_refs={'HGNC': '6407', 'TEXT': 'KRAS'})
    stmts = [sts.Activation(egfr, kras)]
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


def test_get_matching_statements():
    if not CAN_CHECK_STATEMENTS:
        raise SkipTest("Database api not accessible.")
    braf = sts.Agent('BRAF', db_refs={'HGNC': '1097'})
    map2k1 = sts.Agent('MAP2K1', db_refs={'HGNC': '6840'})
    stmt_ref = sts.Phosphorylation(braf, map2k1)
    matching = _get_matching_stmts(stmt_ref)
    assert len(matching) > 1, \
        "Expected > 1 matching, got matching: %s" % matching


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
        assert output.head() == 'SUCCESS',\
            'Expected head SUCCESS, got %s.' % output.to_string()
        assert output.get('model-id') == '1',\
            'Expected model id of \'1\', got \'%s\'' % output.get('model-id')
        assert output.get('model') is not None, 'Got None model.'
        ambiguities = output.get('ambiguities')
        assert len(ambiguities) == 1,\
            "Expcected 1 ambiguity, got %d." % len(ambiguities)
        assert ambiguities[0].get('preferred').to_string() == \
            '(term :ont-type ONT::PROTEIN ' + \
            ':ids "HGNC::6840|NCIT::C52823|UP::Q02750" :name "MAP2K1")'
        expected_fmt = ('(term :ont-type ONT::PROTEIN-FAMILY '
                           ':ids "%s::MAP2K|NCIT::C105947" '
                           ':name "mitogen-activated protein kinase kinase")')
        actual_string = ambiguities[0].get('alternative').to_string()
        assert any([actual_string == expected_fmt % fplx
                    for fplx in ['BE', 'FPLX']]),\
            ("Unexpected ambiguities: expected \"%s\", got \"%s\""
             % (expected_fmt % '<BE or FPLX>', actual_string))
        assert output.get('diagram') is not None, 'Got None for diagram.'
        assert output.gets('diagram').endswith('png'), \
            'Wrong format for diagram.'


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
        stmt = sts.stmts_from_json(indra_stmts_json)[0]
        assert(isinstance(stmt, sts.Phosphorylation))
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
        stmt = sts.stmts_from_json(indra_stmts_json)[0]
        assert(isinstance(stmt, sts.Activation))
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
        output_log = self.get_output_log(get_full_log=True)
        print(output_log)
        assert any([(msg.head() == 'tell') #and 'display' in line)
                    for msg in output_log])


class TestMissingDescriptionFailure(_FailureTest):
    def __init__(self, *args):
        super(TestMissingDescriptionFailure, self).__init__(MRA_Module)
        self.expected_reason = 'INVALID_DESCRIPTION'

    def create_message(self):
        content = KQMLList('BUILD-MODEL')
        content.sets('description', '')
        msg = get_request(content)
        return msg, content


class TestModelBuildExpandUndo(_IntegrationTest):
    def __init__(self, *args):
        super(TestModelBuildExpandUndo, self).__init__(MRA_Module)

    message_funcs = ['build', 'expand', 'undo']

    def create_build(self):
        return _get_build_model_request('KRAS activates BRAF')

    def check_response_to_build(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        model = json.loads(output.gets('model'))
        assert len(model) == 1

    def create_expand(self):
        return _get_expand_model_request('NRAS activates BRAF', '1')

    def check_response_to_expand(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '2'
        model = json.loads(output.gets('model'))
        assert len(model) == 2

    def create_undo(self):
        content = KQMLList('MODEL-UNDO')
        content.sets('model-id', '1')
        msg = get_request(content)
        return msg, content

    def check_response_to_undo(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '3'
        model = json.loads(output.gets('model'))
        assert len(model) == 1



class TestGetModelJson(_IntegrationTest):
    def __init__(self, *args):
        super(TestGetModelJson, self).__init__(MRA_Module)

    message_funcs = ['build', 'get_json']

    def create_build(self):
        return _get_build_model_request('KRAS activates BRAF')

    def check_response_to_build(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        model = json.loads(output.gets('model'))
        assert len(model) == 1

    def create_get_json(self):
        content = KQMLList('MODEL-GET-JSON')
        content.sets('model-id', '1')
        msg = get_request(content)
        return msg, content

    def check_response_to_get_json(self, output):
        assert output.head() == 'SUCCESS'
        model_json = output.gets('model')
        assert model_json
        jd = json.loads(model_json)
        assert len(jd) == 1
        assert jd[0]['type'] == 'Activation'


class TestGetModelJsonNoID(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(MRA_Module)

    message_funcs = ['build', 'get_json']

    def create_build(self):
        return _get_build_model_request('KRAS activates BRAF')

    def check_response_to_build(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        model = json.loads(output.gets('model'))
        assert len(model) == 1

    def create_get_json(self):
        content = KQMLList('MODEL-GET-JSON')
        msg = get_request(content)
        return msg, content

    def check_response_to_get_json(self, output):
        assert output.head() == 'SUCCESS'
        model_json = output.gets('model')
        assert model_json
        jd = json.loads(model_json)
        assert len(jd) == 1
        assert jd[0]['type'] == 'Activation'


class TestModelBuildExpandRemove(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(MRA_Module)

    message_funcs = ['build', 'expand', 'remove', 'remove2']

    def create_build(self):
        return _get_build_model_request('KRAS activates BRAF')

    def check_response_to_build(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        model = json.loads(output.gets('model'))
        assert len(model) == 1

    def create_expand(self):
        return _get_expand_model_request('NRAS activates BRAF', '1')

    def check_response_to_expand(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '2'
        model = json.loads(output.gets('model'))
        assert len(model) == 2

    def create_remove(self):
        content = KQMLList('MODEL-REMOVE-MECHANISM')
        content.set('model-id', '2')
        content.sets('description', ekb_kstring_from_text('KRAS activates BRAF'))
        msg = get_request(content)
        return msg, content

    def check_response_to_remove(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '3'
        model = json.loads(output.gets('model'))
        assert len(model) == 1
        action  = output.get('action')
        assert action.head() == 'remove_stmts'
        rem_stmts_str = action.gets('statements')
        rem_stmts = sts.stmts_from_json(json.loads(rem_stmts_str))
        assert len(rem_stmts) == 1

    def create_remove2(self):
        content = KQMLList('MODEL-REMOVE-MECHANISM')
        content.set('model-id', '3')
        content.sets('description', ekb_kstring_from_text('NRAS activates BRAF'))
        msg = get_request(content)
        return msg, content

    def check_response_to_remove2(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '4'
        model = json.loads(output.gets('model'))
        assert len(model) == 0
        action  = output.get('action')
        assert action.head() == 'remove_stmts'
        rem_stmts_str = action.gets('statements')
        rem_stmts = sts.stmts_from_json(json.loads(rem_stmts_str))
        assert len(rem_stmts) == 1


class TestModelRemoveWrong(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(MRA_Module)

    message_funcs = ['build', 'remove']

    def create_build(self):
        return _get_build_model_request('MEK phosphorylates ERK')

    def check_response_to_build(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        model = json.loads(output.gets('model'))
        assert len(model) == 1

    def create_remove(self):
        content = KQMLList('MODEL-REMOVE-MECHANISM')
        content.set('model-id', '1')
        content.sets('description', ekb_kstring_from_text('Unphosphorylated ERK'))
        msg = get_request(content)
        return msg, content

    def check_response_to_remove(self, output):
        assert output.head() == 'FAILURE', output
        assert output.gets('reason') == 'REMOVE_FAILED', output


class TestModelHasMechanism(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(MRA_Module)

    message_funcs = ['build', 'hasmech1', 'hasmech2']

    def create_build(self):
        return _get_build_model_request('KRAS activates BRAF')

    def check_response_to_build(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        model = json.loads(output.gets('model'))
        assert len(model) == 1

    def create_hasmech1(self):
        content = KQMLList('MODEL-HAS-MECHANISM')
        content.set('model-id', '1')
        content.sets('description', ekb_kstring_from_text('KRAS activates BRAF'))
        msg = get_request(content)
        return msg, content

    def check_response_to_hasmech1(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('has-mechanism') == 'TRUE'

    def create_hasmech2(self):
        content = KQMLList('MODEL-HAS-MECHANISM')
        content.set('model-id', '1')
        content.sets('description', ekb_kstring_from_text('NRAS activates BRAF'))
        msg = get_request(content)
        return msg, content

    def check_response_to_hasmech2(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('has-mechanism') == 'FALSE'


class TestUserGoal(_IntegrationTest):
    def __init__(self, *args):
        super(TestUserGoal, self).__init__(MRA_Module)

    def create_message(self):
        txt = 'Selumetinib decreases FOS in BT20 cells'
        explain = ekb_kstring_from_text(txt)
        content = KQMLList('USER-GOAL')
        content.set('explain', explain)
        msg = get_request(content)
        return msg, content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS'
        assert self.bioagent.mra.context is not None
        assert self.bioagent.mra.explain is not None


class TestModelMeetsGoal(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(MRA_Module)

    message_funcs = ['build', 'expand']

    def create_build(self):
        self.bioagent.mra.explain = \
            sts.Inhibition(sts.Agent('KRAS', db_refs={'HGNC': '6407'}),
                           sts.Agent('MEK', db_refs={'FPLX': 'MEK'}))
        return _get_build_model_request('KRAS activates BRAF')

    def check_response_to_build(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        model = json.loads(output.gets('model'))
        assert len(model) == 1

    def create_expand(self):
        msg = _get_expand_model_request('Active BRAF inhibits MEK.', '1')
        return msg

    def check_response_to_expand(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '2'
        model = json.loads(output.gets('model'))
        assert len(model) == 2
        has_explanation = output.gets('has_explanation')
        assert has_explanation == 'TRUE'


class TestModelMeetsGoalBuildOnly(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(MRA_Module)

    message_funcs = ['build']

    def create_build(self):
        self.bioagent.mra.explain = \
            sts.Activation(sts.Agent('KRAS', db_refs={'HGNC': '6407'}),
                           sts.Agent('BRAF', db_refs={'HGNV': '1097'}))
        return _get_build_model_request('KRAS activates BRAF')

    def check_response_to_build(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        model = json.loads(output.gets('model'))
        assert len(model) == 1
        has_explanation = output.gets('has_explanation')
        assert has_explanation == 'TRUE', has_explanation


class TestModelGapSuggest(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(MRA_Module)

    message_funcs = ['build', 'expand']

    def create_build(self):
        self.bioagent.mra.explain = \
            sts.Activation(sts.Agent('KRAS', db_refs={'HGNC': '6407'}),
                           sts.Agent('JUN', db_refs={'HGNC': '6204'}))
        return _get_build_model_request('KRAS activates MEK.')

    def check_response_to_build(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        model = json.loads(output.gets('model'))
        assert len(model) == 1

    def create_expand(self):
        msg = _get_expand_model_request('Active ERK activates JUN.', '1')
        return msg

    def check_response_to_expand(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '2'
        model = json.loads(output.gets('model'))
        assert len(model) == 2


class TestDegradeSbgn(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(MRA_Module)

    message_funcs = ['build', 'expand']

    def create_build(self):
        return _get_build_model_request('BRAF is degraded.')

    def check_response_to_build(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '1'
        model = json.loads(output.gets('model'))
        assert len(model) == 1

    def create_expand(self):
        return _get_expand_model_request('KRAS is degraded.', '1')

    def check_response_to_expand(self, output):
        assert output.head() == 'SUCCESS'
        assert output.get('model-id') == '2'
        model = json.loads(output.gets('model'))
        assert len(model) == 2



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
