import json
import unittest
from nose.tools import raises
from kqml import KQMLList, KQMLPerformative
from indra.statements import Agent
from .integration import _IntegrationTest
from .test_ekb import _load_kqml
from .util import get_request
from bioagents.tests.util import ekb_from_text
from bioagents.biosense.biosense_module import BioSense_Module
from bioagents.biosense.biosense import BioSense, InvalidAgentError, \
    InvalidCollectionError, UnknownCategoryError, \
    CollectionNotFamilyOrComplexError, SynonymsUnknownError


class TestGetIndraRepresentationOneAgent(_IntegrationTest):
    def __init__(self, *args):
        super().__init__(BioSense_Module)

    def create_message(self):
        kql = KQMLList.from_string(_load_kqml('tofacitinib.kqml'))
        content = KQMLList('get-indra-representation')
        content.set('context', kql)
        content.set('ids', KQMLList(['V34850']))
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'done'
        res = output.get('result')
        assert res
        agent = self.bioagent.get_agent(res)
        assert agent.name == 'TOFACITINIB'


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


# example ekb terms
mek1_ekb = ekb_from_text('MAP2K1')  # agent
dusp_ekb = ekb_from_text('DUSP6')  # agent
mek_ekb = ekb_from_text('MEK')  # family
foo_ekb = ekb_from_text('foo')  # invalid


# BioSense python API unit tests
def test_choose_sense():
    bs = BioSense()
    cases = [(mek1_ekb, 'MAP2K1', 'ONT::GENE'),
             (dusp_ekb, 'DUSP6', 'ONT::GENE'),
             (mek_ekb, 'MEK', 'ONT::PROTEIN-FAMILY')]
    for case in cases:
        agents, _ = bs.choose_sense(case[0])
        agent, ont_type, _ = list(agents.values())[0]
        assert agent.name == case[1]
        assert ont_type == case[2]


@raises(InvalidAgentError)
def test_choose_sense_invalid_agent():
    """should raise InvalidAgentError if the agent is not recognized"""
    bs = BioSense()
    invalid_case = foo_ekb
    bs.choose_sense(invalid_case)


def test_choose_nonsense():
    """ekb terms that aren't biological agents should have ont-type None

    BAGEL is from ONT::BAGELS-BISCUITS
    """
    bs = BioSense()
    case = ekb_from_text('bagel')
    agents, _ = bs.choose_sense(case)
    _, ont_type, _ = list(agents.values())[0]
    assert ont_type is None


def test_choose_sense_category():
    bs = BioSense()
    cases = [(mek1_ekb, [('kinase activity', 'TRUE'),
                         ('enzyme', 'TRUE'),
                         ('kinase', 'TRUE'),
                         ('transcription-factor', 'FALSE'),
                         ('W::KINASE', 'TRUE'),
                         ('phosphatase', 'FALSE')]),
             (dusp_ekb, [('phosphatase', 'TRUE'), ('enzyme', 'TRUE')]),
             (ekb_from_text('BRAF'), [('kinase', 'TRUE')])]
    for ekb, result_tuples in cases:
        for cat, result in result_tuples:
            print('Testing: %s. Expect result %s.' % (cat, result))
            in_category = bs.choose_sense_category(ekb, cat)
            assert in_category == (result == 'TRUE')


@raises(InvalidAgentError)
def test_choose_sense_category_invalid_agent():
    """should raise InvalidAgentError if the agent is not recognized"""
    bs = BioSense()
    bs.choose_sense_category(foo_ekb, 'kinase activity')


@raises(UnknownCategoryError)
def test_choose_sense_category_unknown_category():
    """should raise UnknownCategoryError if the category is not recognized"""
    bs = BioSense()
    bs.choose_sense_category(mek1_ekb, 'foo')


def test_choose_sense_is_member():
    bs = BioSense()
    cases = [(mek1_ekb, mek_ekb, True),
             (dusp_ekb, mek_ekb, False)]
    for (agent, collection, result) in cases:
        assert bs.choose_sense_is_member(agent, collection) == result


@raises(CollectionNotFamilyOrComplexError)
def test_choose_sense_is_member_not_family_or_complex():
    """raises CollectionNotFamilyOrComplexError if the collection we test
    membership in is not a family or complex
    """
    bs = BioSense()
    bs.choose_sense_is_member(mek_ekb, mek1_ekb)


@raises(InvalidAgentError)
def test_choose_sense_is_member_invalid_agent():
    """raises InvalidAgentError if the agent is not recognized"""
    bs = BioSense()
    bs.choose_sense_is_member(foo_ekb, mek_ekb)


@raises(InvalidCollectionError)
def test_choose_sense_is_member_invalid_collection():
    """raises InvalidCollectionError if the collection we are testing
    membership in is not recognized
    """
    bs = BioSense()
    bs.choose_sense_is_member(mek1_ekb, foo_ekb)


def test_choose_sense_what_member():
    bs = BioSense()
    members = bs.choose_sense_what_member(mek_ekb)
    member_names = [agent.name for agent in members]
    result = ['MAP2K1', 'MAP2K2']
    assert member_names == result


@raises(CollectionNotFamilyOrComplexError)
def test_choose_sense_what_member_not_family_or_complex():
    bs = BioSense()
    bs.choose_sense_what_member(mek1_ekb)


@raises(InvalidCollectionError)
def test_choose_sense_what_member_invalid_collection():
    bs = BioSense()
    bs.choose_sense_what_member(foo_ekb)


def test_get_synonyms():
    bs = BioSense()
    example_synonyms = {'PRKMK1', 'MEK1', 'MAP2K1', 'ERK activator kinase 1',
                        'MKK1', 'MEK 1'}
    synonyms = set(bs.get_synonyms(mek1_ekb))
    assert example_synonyms.issubset(synonyms)


def test_get_synonyms_fplx():
    bs = BioSense()
    example_synonyms = {'MEK', 'MEK1/2', 'MEK 1/2'}
    synonyms = set(bs.get_synonyms(mek_ekb))
    assert example_synonyms.issubset(synonyms), synonyms


@raises(InvalidAgentError)
def test_get_synonyms_invalid_agent():
    """raises InvalidAgentError when the agent is not recognized or if the
    input submitted is not valid XML or is not in the correct format
    """
    bs = BioSense()
    # xml missing TERM attribute
    invalid1 = mek1_ekb.replace('TERM', 'TREM')
    # xml not an ekb
    invalid2 = """
    <student>
    <equal>slabs</equal>
    <biggest>
      <opportunity>available</opportunity>
    <save money="suddenly">1477118976.7289777</save>
      <industrial>hand</industrial>
      <mysterious>modern</mysterious>
    <dig mark="toward">-1425890046.2266533</dig>
      <wash vowel="wolf">-206507947</wash>
    </biggest>
    <especially its="character">all</especially>
    <because>999696668</because>
    <away blue="against">-269919679</away>
    <younger>include</younger>
    </student>
    <through>-413227646</through>
    <tip>opportunity</tip>
    <doll slow="serve">broad</doll>
    <card gold="parallel">1517689761</card>
    </root>
    """
    # string not xml
    invalid3 = ""
    bs.get_synonyms(invalid1)
    bs.get_synonyms(invalid2)
    bs.get_synonyms(invalid3)


@raises(SynonymsUnknownError)
def test_get_synonyms_no_synonyms_for_type():
    """raises InvalidAgentError when the agent is not recognized or if the
    input submitted is not valid XML or is not in the correct format
    """
    bs = BioSense()
    bs.get_synonyms(ekb_from_text('vemurafenib'))


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
