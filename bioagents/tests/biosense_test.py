import unittest
from nose.tools import raises
from kqml import KQMLList
from indra.statements import Phosphorylation, Agent, Statement, \
    Dephosphorylation, Complex, ActiveForm, Activation, IncreaseAmount
from .integration import _IntegrationTest
from .test_ekb import _load_kqml
from bioagents import Bioagent
from bioagents.biosense.biosense_module import BioSense_Module
from bioagents.biosense.biosense import BioSense, UnknownCategoryError, \
    CollectionNotFamilyOrComplexError, SynonymsUnknownError
from bioagents.tests.util import get_request, agent_clj_from_text


class TestChooseSense(_IntegrationTest):
    def __init__(self, *args):
        super().__init__(BioSense_Module)

    def create_message(self):
        content = KQMLList('CHOOSE-SENSE')
        agent = agent_clj_from_text('BRAF')
        content.set('agent', agent)
        print(content)
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head().lower() == 'success', output
        print(output)
        agent = output.get('agent')
        assert agent
        urls = output.get('id-urls')
        assert len(urls) == 3
        desc = output.gets('description')
        assert 'thereby activates the MAP' in desc, desc


class _GetIndraRepTemplate(_IntegrationTest):
    kqml_file = NotImplemented

    def __init__(self, *args):
        super().__init__(BioSense_Module)

    def create_message(self):
        content = KQMLList.from_string(_load_kqml(self.kqml_file))
        assert content.head().upper() == 'GET-INDRA-REPRESENTATION'
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'done'
        res = output.get('result')
        assert res, output
        self.check_result(res)

    def check_result(self, res):
        raise NotImplementedError("This function must be defined by each test")


class TestGetIndraRepOneAgent(_GetIndraRepTemplate):
    kqml_file = 'tofacitinib.kqml'

    def check_result(self, res):
        agent = self.bioagent.get_agent(res)
        assert agent.name == 'TOFACITINIB'
        assert agent.db_refs['TRIPS'] == 'ONT::V34850'
        assert agent.db_refs['TYPE'] == 'ONT::PHARMACOLOGIC-SUBSTANCE', \
            agent.db_refs


class TestGetIndraRepTwoSubtrates(_GetIndraRepTemplate):
    kqml_file = 'mek_phos_erk1_erk2.kqml'

    def check_result(self, res):
        stmts = self.bioagent.get_statement(res)
        assert len(stmts) == 2
        assert isinstance(stmts[0], Phosphorylation)
        assert isinstance(stmts[1], Phosphorylation)
        assert stmts[0].enz.name == 'MEK'
        assert stmts[1].enz.name == 'MEK'
        assert {stmts[0].sub.name, stmts[1].sub.name} == \
            {'MAPK1', 'MAPK3'}, stmts


class TestGetIndraRepMixedPathways(_GetIndraRepTemplate):
    kqml_file = 'wnt_mapk_signaling.kqml'

    def check_result(self, res):
        agent = self.bioagent.get_agent(res)
        # It should be about MAPK not Wnt
        assert agent.name == 'mapk signaling pathway'
        assert agent.db_refs['TYPE'] == 'ONT::SIGNALING-PATHWAY'


class TestGetIndraRepOneAgent2(_GetIndraRepTemplate):
    kqml_file = 'selumetinib.kqml'

    def check_result(self, res):
        agent = self.bioagent.get_agent(res)
        assert agent.name == 'SELUMETINIB'
        assert agent.db_refs['TRIPS'] == 'ONT::V34821', agent.db_refs
        assert agent.db_refs['TYPE'] == 'ONT::PHARMACOLOGIC-SUBSTANCE'


class TestGetIndraRepStatement(_GetIndraRepTemplate):
    kqml_file = 'braf_phos_mek_site_pos.kqml'

    def check_result(self, res):
        stmts = self.bioagent.get_statement(res)
        assert len(stmts) == 1
        stmt = stmts[0]
        assert isinstance(stmt, Phosphorylation)
        assert stmt.enz.name == 'BRAF'
        assert stmt.sub.name == 'MAP2K1'
        assert stmt.residue == 'S'
        assert stmt.position == '222', stmt.position


"""res is still empty so this errors
class TestGetIndraRepCCStatement(_GetIndraRepTemplate):
    kqml_file = 'perk_proliferation.kqml'

    def check_result(self, res):
        # No statements at this point because this is
        # a CC between two terms but at least we shouldn't
        # error
        pass
"""


class TestGetIndraRepIncreaseBP(_GetIndraRepTemplate):
    kqml_file = 'increase_progression.kqml'

    def check_result(self, res):
        # No statements at this point because this is
        # a CC between two terms but at least we shouldn't
        # error
        pass


class TestSB525334(_GetIndraRepTemplate):
    kqml_file = 'SB525334.kqml'

    def check_result(self, res):
        stmt = self.bioagent.get_statement(res)[0]
        assert stmt.subj.name == 'SB-525334'


class TestGetIndraRepMultipleResults(_GetIndraRepTemplate):
    kqml_file = 'multiple_results.kqml'

    def check_result(self, res):
        agents = self.bioagent.get_agent(res)
        assert len(agents) == 3, len(agents)
        name_set = {ag.name for ag in agents}
        assert name_set == {'HRAS', 'SRF', 'ELK1'}, name_set
        assert all(ag.db_refs for ag in agents), [ag.db_refs for ag in agents]
        assert all('TRIPS' in ag.db_refs.keys()
                   and ag.db_refs['TRIPS'].startswith('ONT::V')
                   for ag in agents), [ag.db_refs for ag in agents]


class TestGetIndraRepMIRNA(_GetIndraRepTemplate):
    kqml_file = 'mirna.kqml'

    def check_result(self, res):
        agent = self.bioagent.get_agent(res)
        assert agent.name == 'MIR-20B-5P', agent.name
        assert agent.db_refs['TYPE'] == 'ONT::RNA'
        assert agent.db_refs['TEXT'] == 'MIR-PUNC-MINUS-20-B-PUNC-MINUS-5-P'
        assert agent.db_refs['TRIPS'] == 'ONT::V36357'


class TestGetIndraRepPathwayMAPKSimple(_GetIndraRepTemplate):
    kqml_file = 'MAPK_signaling_pathway_simple.kqml'

    def check_result(self, res):
        agent = self.bioagent.get_agent(res)
        assert isinstance(agent, Agent), agent
        assert agent.name == 'MAPK signaling pathway', agent.name
        assert agent.db_refs['TYPE'] == 'ONT::SIGNALING-PATHWAY', agent.db_refs
        assert agent.db_refs['TRIPS'].startswith('ONT::'), agent.db_refs
        assert agent.db_refs['FPLX'] == 'MAPK', agent.db_refs
        assert agent.db_refs['NCIT'], agent.db_refs


class TestGetIndraRepPathwayMAPKCompound(_GetIndraRepTemplate):
    kqml_file = 'MAPK_signaling_pathway_compound.kqml'

    def check_result(self, res):
        agent = self.bioagent.get_agent(res)
        assert isinstance(agent, Agent), agent
        assert agent.name == 'MAPK signaling pathway', agent.name
        assert agent.db_refs['TYPE'] == 'ONT::SIGNALING-PATHWAY', agent.db_refs
        assert agent.db_refs['TRIPS'].startswith('ONT::'), agent.db_refs
        assert agent.db_refs['FPLX'] == 'MAPK', agent.db_refs
        assert agent.db_refs['NCIT'], agent.db_refs


class TestGetIndraRepPathwayMTOR(_GetIndraRepTemplate):
    kqml_file = 'mtor_pathway.kqml'

    def check_result(self, res):
        agent = self.bioagent.get_agent(res)
        assert isinstance(agent, Agent), agent
        assert agent.name == 'MTOR signaling pathway', agent.name
        assert agent.db_refs['TYPE'] == 'ONT::SIGNALING-PATHWAY', agent.db_refs
        assert agent.db_refs['TRIPS'].startswith('ONT::'), agent.db_refs
        assert agent.db_refs['HGNC'] == '3942', agent.db_refs
        assert agent.db_refs['NCIT'], agent.db_refs


class TestGetIndraRepPathwayImmuneSystem(_GetIndraRepTemplate):
    kqml_file = 'immune_system_pathway.kqml'

    def check_result(self, res):
        agent = self.bioagent.get_agent(res)
        assert isinstance(agent, Agent), type(agent)
        assert agent.name == 'immune system signaling pathway', agent.name
        assert agent.db_refs['TYPE'] == 'ONT::SIGNALING-PATHWAY', agent.db_refs
        assert agent.db_refs['TRIPS'].startswith('ONT::'), agent.db_refs


class TestGetIndraRepDephosphorylation(_GetIndraRepTemplate):
    kqml_file = 'dephosphorylation.kqml'

    def check_result(self, res):
        stmts = self.bioagent.get_statement(res)
        assert len(stmts) == 1
        assert isinstance(stmts[0], Dephosphorylation), stmts


class TestGetIndraRepComplexEntities(_GetIndraRepTemplate):
    kqml_file = 'complex_entities.kqml'

    def check_result(self, res):
        stmts = self.bioagent.get_statement(res)
        assert len(stmts) == 1
        assert isinstance(stmts[0], Complex), stmts
        stmt = stmts[0]
        assert len(stmt.members) == 2
        agents = {m.name: m for m in stmt.members}
        assert 'EGFR' in agents
        assert 'GRB2' in agents
        assert agents['EGFR'].bound_conditions
        assert agents['EGFR'].bound_conditions[0].agent.name == 'EGFR'
        assert agents['EGFR'].bound_conditions[0].is_bound is True


@unittest.skip('Cell line extraction not working yet')
class TestGetIndraRepCellLineContext(_GetIndraRepTemplate):
    kqml_file = 'cell_line_context.kqml'

    def check_result(self, res):
        stmts = self.bioagent.get_statement(res)
        assert len(stmts) == 1, len(stmts)
        stmt = stmts[0]
        assert isinstance(stmt, Statement), type(stmt)
        assert len(stmt.evidence) == 1, len(stmt.evidence)
        ev = stmt.evidence[0]
        assert ev.context, ev.context


class TestGetIndraRepAddMechanismRecursion(_GetIndraRepTemplate):
    kqml_file = 'very_specific_model_addition.kqml'

    def check_result(self, res):
        stmts = self.bioagent.get_statement(res)
        assert len(stmts) == 1, stmts
        assert isinstance(stmts[0], Dephosphorylation)
        assert stmts[0].enz.name == 'PPP2CA', stmts[0].enz
        assert stmts[0].sub.name == 'MAP2K1'
        assert len(stmts[0].sub.bound_conditions) == 1
        assert stmts[0].sub.bound_conditions[0].agent.name == 'MAPK1'
        assert stmts[0].sub.bound_conditions[0].is_bound is False


class TestGetIndraRepPhosphorylatedMAPK1IsActive(_GetIndraRepTemplate):
    kqml_file = 'phosphorylated_mapk1_is_active.kqml'

    def check_result(self, res):
        stmts = self.bioagent.get_statement(res)
        assert len(stmts) == 1, stmts
        stmt = stmts[0]
        assert isinstance(stmt, ActiveForm), type(stmt)
        assert stmt.is_active, stmt
        assert stmt.agent.name == 'MAPK1', stmt
        assert len(stmt.agent.mods) == 1, stmt.agent
        mod = stmt.agent.mods[0]
        assert mod.is_modified, mod
        assert mod.mod_type == 'phosphorylation', mod
        assert mod.position is None, mod


class TestGetIndraRepDUSPDephosphorylatesMAPK1onT185(_GetIndraRepTemplate):
    kqml_file = 'DUSP_dephosphorylates_MAPK1_on_T185.kqml'

    def check_result(self, res):
        stmts = self.bioagent.get_statement(res)
        assert len(stmts) == 1, stmts
        stmt = stmts[0]
        assert isinstance(stmt, Dephosphorylation), type(stmt)
        assert stmt.enz.name == 'DUSP', stmt
        assert stmt.sub.name == 'MAPK1', stmt
        assert stmt.position == '185', stmt.position
        assert stmt.residue == 'T', stmt.residue


class TestGetIndraRepActiveMAPK1ActivatesELK1(_GetIndraRepTemplate):
    kqml_file = 'Active_MAPK1_activates_ELK1.kqml'

    def check_result(self, res):
        stmts = self.bioagent.get_statement(res)
        assert len(stmts) == 1, stmts
        stmt = stmts[0]
        assert isinstance(stmt, Activation), type(stmt)
        assert stmt.subj.name == 'MAPK1', stmt
        assert stmt.obj.name == 'ELK1', stmt
        assert stmt.subj.activity.is_active, stmt.subj


class TestGetIndraRepActiveELK1TranscribesFOS(_GetIndraRepTemplate):
    kqml_file = 'Active_ELK1_transcribes_FOS.kqml'

    def check_result(self, res):
        stmts = self.bioagent.get_statement(res)
        assert len(stmts) == 1, stmts
        stmt = stmts[0]
        assert isinstance(stmt, IncreaseAmount), type(stmt)
        assert stmt.subj.name == 'ELK1', stmt
        assert stmt.obj.name == 'FOS', stmt
        assert stmt.subj.activity.is_active, stmt.subj


class TestGetIndraRepInactiveRAFActivatesMEK(_GetIndraRepTemplate):
    kqml_file = 'Inactive_RAF_activates_MEK.kqml'

    def check_result(self, res):
        stmts = self.bioagent.get_statement(res)
        assert len(stmts) == 1, stmts
        stmt = stmts[0]
        assert isinstance(stmt, Activation), type(stmt)
        assert stmt.subj.name == 'RAF', stmt
        assert stmt.subj.activity, stmt
        assert not stmt.subj.activity.is_active, stmt
        assert stmt.obj.name == 'MEK', stmt


mek1 = agent_clj_from_text('MEK1')
mek1a = Bioagent.get_agent(mek1)
mek = agent_clj_from_text('MEK')
meka = Bioagent.get_agent(mek)
dusp6 = agent_clj_from_text('DUSP6')
dusp6a = Bioagent.get_agent(dusp6)
braf = agent_clj_from_text('BRAF')
brafa = Bioagent.get_agent(braf)

bs = BioSense()


def test_choose_sense_category():
    cases = [(mek1a, [('kinase activity', 'TRUE'),
                      ('enzyme', 'TRUE'),
                      ('kinase', 'TRUE'),
                      ('transcription-factor', 'FALSE'),
                      ('W::KINASE', 'TRUE'),
                      ('phosphatase', 'FALSE')]),
             (dusp6a, [('phosphatase', 'TRUE'), ('enzyme', 'TRUE')]),
             (brafa, [('kinase', 'TRUE')])]
    for agent, result_tuples in cases:
        for cat, result in result_tuples:
            print('Testing: %s. Expect result %s.' % (cat, result))
            in_category = bs.choose_sense_category(agent, cat)
            assert in_category == (result == 'TRUE')


@raises(UnknownCategoryError)
def test_choose_sense_category_unknown_category():
    """should raise UnknownCategoryError if the category is not recognized"""
    bs.choose_sense_category(mek1a, 'foo')


def test_choose_sense_is_member():
    cases = [(mek1a, meka, True),
             (dusp6a, meka, False)]
    for (agent, collection, result) in cases:
        assert bs.choose_sense_is_member(agent, collection) == result


@raises(CollectionNotFamilyOrComplexError)
def test_choose_sense_is_member_not_family_or_complex():
    """raises CollectionNotFamilyOrComplexError if the collection we test
    membership in is not a family or complex
    """
    bs.choose_sense_is_member(meka, mek1a)


@raises(CollectionNotFamilyOrComplexError)
def test_choose_sense_is_member_invalid_collection():
    """raises InvalidCollectionError if the collection we are testing
    membership in is not recognized
    """
    bs.choose_sense_is_member(mek1a, dusp6a)


def test_choose_sense_what_member():
    members = bs.choose_sense_what_member(meka)
    member_names = [agent.name for agent in members]
    result = ['MAP2K1', 'MAP2K2']
    assert member_names == result


@raises(CollectionNotFamilyOrComplexError)
def test_choose_sense_what_member_not_family_or_complex():
    bs.choose_sense_what_member(mek1a)


def test_get_synonyms():
    example_synonyms = {'PRKMK1', 'MEK1', 'MAP2K1', 'ERK activator kinase 1',
                        'MKK1', 'MEK 1'}
    synonyms = set(bs.get_synonyms(mek1a))
    assert example_synonyms.issubset(synonyms)


def test_get_synonyms_fplx():
    example_synonyms = {'MEK', 'MEK1/2', 'MEK 1/2'}
    synonyms = set(bs.get_synonyms(meka))
    assert example_synonyms.issubset(synonyms), synonyms


def test_get_synonyms_chemical():
    """raises InvalidAgentError when the agent is not recognized or if the
    input submitted is not valid XML or is not in the correct format
    """
    synonyms = bs.get_synonyms(Bioagent.get_agent(
        agent_clj_from_text('vemurafenib')))
    assert synonyms


@raises(SynonymsUnknownError)
def test_get_synonyms_ungrounded():
    """raises InvalidAgentError when the agent is not recognized or if the
    input submitted is not valid XML or is not in the correct format
    """
    bs.get_synonyms(Agent('x', db_refs={'xxx': '123'}))


# BioSense module unit tests
def test_respond_choose_sense():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('CHOOSE-SENSE')
    msg_content.set('agent', mek1)
    res = bs.respond_choose_sense(msg_content)
    agent_clj = res.get('agent')
    assert agent_clj
    agent = Bioagent.get_agent(agent_clj)
    assert agent.name == 'MAP2K1'
    assert agent.db_refs['HGNC'] == '6840'


def test_respond_choose_nonsense():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('CHOOSE-SENSE')
    msg_content.set('agent', agent_clj_from_text('bagel'))
    res = bs.respond_choose_sense(msg_content)
    print(res)
    assert res.head() == 'SUCCESS'
    agents_clj = res.get('agent')
    agent = Bioagent.get_agent(agents_clj)
    assert agent.name == 'BAGEL'
    assert len(agent.db_refs) == 1


def test_respond_choose_sense_category():
    bs = BioSense_Module(testing=True)
    cases = [(mek1, [('kinase activity', 'TRUE'),
                     ('enzyme', 'TRUE'),
                     ('kinase', 'TRUE'),
                     ('transcription-factor', 'FALSE'),
                     ('W::KINASE', 'TRUE'),
                     ('phosphatase', 'FALSE')]),
             (dusp6, [('phosphatase', 'TRUE'), ('enzyme', 'TRUE')]),
             (braf, [('kinase', 'TRUE')])]
    for agent_clj, result_tuples in cases:
        msg_content = KQMLList('CHOOSE-SENSE-CATEGORY')
        msg_content.set('ekb-term', agent_clj)
        for cat, result in result_tuples:
            print('Testing: %s. Excpet result %s.' % (cat, result))
            msg_content.sets('category', cat)
            res = bs.respond_choose_sense_category(msg_content)
            print(res)
            print(res.head())
            assert(res.head() == 'SUCCESS')
            assert(res.get('in-category') == result)


def test_respond_choose_sense_is_member():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('CHOOSE-SENSE-IS-MEMBER')
    msg_content.set('ekb-term', mek1)
    msg_content.set('collection', mek)
    print(msg_content)
    res = bs.respond_choose_sense_is_member(msg_content)
    print(res)
    print(res.head())
    assert(res.head() == 'SUCCESS')
    assert(res.get('is-member') == 'TRUE')


def test_respond_choose_sense_what_member():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('CHOOSE-SENSE-WHAT-MEMBER')
    msg_content.set('collection', mek)
    print(msg_content)
    res = bs.respond_choose_sense_what_member(msg_content)
    print(res)
    print(res.head())
    assert(res.head() == 'SUCCESS')
    assert(len(res.get('members')) == 2)
    m1 = res.get('members')[0]
    m2 = res.get('members')[1]
    a1 = Bioagent.get_agent(m1)
    a2 = Bioagent.get_agent(m2)
    assert a1.name == 'MAP2K1'
    assert a2.name == 'MAP2K2'
    assert a2.db_refs['HGNC'] == '6842'
    assert a1.db_refs['UP'] == 'Q02750'


def test_respond_get_synonyms():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('GET-SYNONYMS')
    msg_content.set('entity', mek1)
    res = bs.respond_get_synonyms(msg_content)
    assert res.head() == 'SUCCESS'
    syns = res.get('synonyms')
    syn_strs = [s.gets(':name') for s in syns]
    assert 'MAP2K1' in syn_strs, syn_strs
    assert 'MEK1' in syn_strs, syn_strs
    assert 'MKK1' in syn_strs, syn_strs
    assert res.get('num_synonyms') == '23', res
