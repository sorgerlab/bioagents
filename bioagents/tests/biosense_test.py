import unittest
from nose.tools import raises
from kqml import KQMLList
from indra.statements import Phosphorylation
from .integration import _IntegrationTest
from .test_ekb import _load_kqml
from bioagents.biosense.biosense_module import BioSense_Module
from bioagents.biosense.biosense import BioSense, InvalidAgentError, \
    InvalidCollectionError, UnknownCategoryError, \
    CollectionNotFamilyOrComplexError, SynonymsUnknownError
from bioagents.tests.util import ekb_from_text, get_request, agent_clj_from_text


class TestGetIndraRepresentationOneAgent(_IntegrationTest):
    def __init__(self, *args):
        super().__init__(BioSense_Module)

    def create_message(self):
        kql = KQMLList.from_string(_load_kqml('tofacitinib.kqml'))
        content = KQMLList('get-indra-representation')
        content.set('context', kql)
        content.set('ids', KQMLList(['ONT::V34850']))
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'done'
        res = output.get('result')
        assert res
        agent = self.bioagent.get_agent(res)
        assert agent.name == 'TOFACITINIB'
        assert agent.db_refs['TRIPS'] == 'ONT::V34850'
        assert agent.db_refs['TYPE'] == 'ONT::PHARMACOLOGIC-SUBSTANCE', \
            agent.db_refs


class TestGetIndraRepresentationOneAgent2(_IntegrationTest):
    def __init__(self, *args):
        super().__init__(BioSense_Module)

    def create_message(self):
        content = KQMLList.from_string(_load_kqml('selumetinib.kqml'))
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'done'
        res = output.get('result')
        assert res
        agent = self.bioagent.get_agent(res)
        assert agent.name == 'SELUMETINIB'
        assert agent.db_refs['TRIPS'] == 'ONT::V34821', agent.db_refs
        assert agent.db_refs['TYPE'] == 'ONT::PHARMACOLOGIC-SUBSTANCE'


class TestGetIndraRepresentationStatement(_IntegrationTest):
    def __init__(self, *args):
        super().__init__(BioSense_Module)

    def create_message(self):
        content = KQMLList.from_string(_load_kqml('braf_phos_mek_site_pos.kqml'))
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'done', output
        res = output.get('result')
        assert res
        stmts = self.bioagent.get_statement(res)
        assert len(stmts) == 1
        stmt = stmts[0]
        assert isinstance(stmt, Phosphorylation)
        assert stmt.enz.name == 'BRAF'
        assert stmt.sub.name == 'MAP2K1'
        assert stmt.residue == 'S'
        assert stmt.position == '222', stmt.position


mek1 = agent_clj_from_text('MEK1')
mek = agent_clj_from_text('MEK')
dusp6 = agent_clj_from_text('DUSP6')
braf = agent_clj_from_text('BRAF')
bs = BioSense()


def test_choose_sense_category():
    cases = [(mek1, [('kinase activity', 'TRUE'),
                     ('enzyme', 'TRUE'),
                     ('kinase', 'TRUE'),
                     ('transcription-factor', 'FALSE'),
                     ('W::KINASE', 'TRUE'),
                     ('phosphatase', 'FALSE')]),
             (dusp6, [('phosphatase', 'TRUE'), ('enzyme', 'TRUE')]),
             (braf, [('kinase', 'TRUE')])]
    for agent, result_tuples in cases:
        for cat, result in result_tuples:
            print('Testing: %s. Expect result %s.' % (cat, result))
            in_category = bs.choose_sense_category(agent, cat)
            assert in_category == (result == 'TRUE')


@raises(UnknownCategoryError)
def test_choose_sense_category_unknown_category():
    """should raise UnknownCategoryError if the category is not recognized"""
    bs.choose_sense_category(mek1, 'foo')


def test_choose_sense_is_member():
    cases = [(mek1, mek, True),
             (dusp6, mek, False)]
    for (agent, collection, result) in cases:
        assert bs.choose_sense_is_member(agent, collection) == result


@raises(CollectionNotFamilyOrComplexError)
def test_choose_sense_is_member_not_family_or_complex():
    """raises CollectionNotFamilyOrComplexError if the collection we test
    membership in is not a family or complex
    """
    bs.choose_sense_is_member(mek, mek1)


@raises(InvalidCollectionError)
def test_choose_sense_is_member_invalid_collection():
    """raises InvalidCollectionError if the collection we are testing
    membership in is not recognized
    """
    bs.choose_sense_is_member(mek1, dusp6)


def test_choose_sense_what_member():
    members = bs.choose_sense_what_member(mek)
    member_names = [agent.name for agent in members]
    result = ['MAP2K1', 'MAP2K2']
    assert member_names == result


@raises(CollectionNotFamilyOrComplexError)
def test_choose_sense_what_member_not_family_or_complex():
    bs.choose_sense_what_member(mek1)


def test_get_synonyms():
    example_synonyms = {'PRKMK1', 'MEK1', 'MAP2K1', 'ERK activator kinase 1',
                        'MKK1', 'MEK 1'}
    synonyms = set(bs.get_synonyms(mek1))
    assert example_synonyms.issubset(synonyms)


def test_get_synonyms_fplx():
    example_synonyms = {'MEK', 'MEK1/2', 'MEK 1/2'}
    synonyms = set(bs.get_synonyms(mek))
    assert example_synonyms.issubset(synonyms), synonyms


@raises(SynonymsUnknownError)
def test_get_synonyms_no_synonyms_for_type():
    """raises InvalidAgentError when the agent is not recognized or if the
    input submitted is not valid XML or is not in the correct format
    """
    bs.get_synonyms(agent_clj_from_text('vemurafenib'))


# BioSense module unit tests
def test_respond_choose_sense():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('CHOOSE-SENSE')
    msg_content.sets('ekb-term', mek1_ekb)
    res = bs.respond_choose_sense(msg_content)
    print(res)
    agents = res.get('agents')
    assert agents and agents.data
    agent = agents[0]
    name = agent.gets('name')
    assert name == 'MAP2K1'
    ont_type = agent.get('ont-type')
    assert ont_type == 'ONT::GENE'
    description = agent.gets('description')
    assert 'Dual specificity' in description


def test_respond_choose_nonsense():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('CHOOSE-SENSE')
    msg_content.sets('ekb-term', ekb_from_text('bagel'))
    res = bs.respond_choose_sense(msg_content)
    print(res)
    assert res.head() == 'SUCCESS'
    assert res.get('agents')[0].gets('ont-type') is None


@unittest.skip('No ambiguity reported here yet')
def test_respond_choose_sense_ambiguity():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('CHOOSE-SENSE')
    pdk1_ekb = ekb_from_text('PDK1')
    msg_content.sets('ekb-term', pdk1_ekb)
    res = bs.respond_choose_sense(msg_content)
    print(res)
    agents = res.get('agents')
    assert agents and agents.data
    agent = agents[0]
    name = agent.gets('name')
    assert name == 'PDK1'
    ont_type = agent.get('ont-type')
    assert ont_type == 'ONT::GENE'


def test_respond_choose_sense_category():
    bs = BioSense_Module(testing=True)
    cases = [(mek1_ekb, [('kinase activity', 'TRUE'),
                         ('enzyme', 'TRUE'),
                         ('kinase', 'TRUE'),
                         ('transcription-factor', 'FALSE'),
                         ('W::KINASE', 'TRUE'),
                         ('phosphatase', 'FALSE')]),
             (dusp_ekb, [('phosphatase', 'TRUE'), ('enzyme', 'TRUE')]),
             (ekb_from_text('BRAF'), [('kinase', 'TRUE')])]
    for ekb, result_tuples in cases:
        msg_content = KQMLList('CHOOSE-SENSE-CATEGORY')
        msg_content.sets('ekb-term', ekb)
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
    msg_content.sets('ekb-term', mek1_ekb)
    msg_content.sets('collection', mek_ekb)
    print(msg_content)
    res = bs.respond_choose_sense_is_member(msg_content)
    print(res)
    print(res.head())
    assert(res.head() == 'SUCCESS')
    assert(res.get('is-member') == 'TRUE')


def test_respond_choose_sense_what_member():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('CHOOSE-SENSE-WHAT-MEMBER')
    msg_content.sets('collection', mek_ekb)
    print(msg_content)
    res = bs.respond_choose_sense_what_member(msg_content)
    print(res)
    print(res.head())
    assert(res.head() == 'SUCCESS')
    assert(len(res.get('members')) == 2)
    m1 = res.get('members')[0]
    m2 = res.get('members')[1]
    assert m1.gets('name') == 'MAP2K1', m1.gets('name')
    assert m2.gets('name') == 'MAP2K2', m2.gets('name')


def test_respond_get_synonyms():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('GET-SYNONYMS')
    msg_content.sets('entity', mek1_ekb)
    res = bs.respond_get_synonyms(msg_content)
    assert res.head() == 'SUCCESS'
    syns = res.get('synonyms')
    syn_strs = [s.gets(':name') for s in syns]
    assert 'MAP2K1' in syn_strs
    assert 'MEK1' in syn_strs
    assert 'MKK1' in syn_strs
