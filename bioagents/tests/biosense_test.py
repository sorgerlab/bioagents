import unittest
from nose.tools import raises
from kqml import KQMLList
from indra.statements import Phosphorylation, Agent
from .util import agent_clj_from_text
from .integration import _IntegrationTest
from .test_ekb import _load_kqml
from bioagents import Bioagent
from bioagents.biosense.biosense_module import BioSense_Module
from bioagents.biosense.biosense import BioSense, InvalidAgentError, \
    InvalidCollectionError, UnknownCategoryError, \
    CollectionNotFamilyOrComplexError, SynonymsUnknownError
from bioagents.tests.util import ekb_from_text, get_request, agent_clj_from_text


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
        assert 'thereby contributes to the MAP' in desc, desc


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
        content = KQMLList.from_string(
            _load_kqml('braf_phos_mek_site_pos.kqml'))
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


class TestGetIndraRepresentationPathwayMAPKSimple(_IntegrationTest):
    def __init__(self, *args):
        super().__init__(BioSense_Module)

    def create_message(self):
        content = KQMLList.from_string(
            _load_kqml('MAPK_signaling_pathway_simple.kqml')
        )
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'done', output
        res = output.get('result')
        assert res
        agent = self.bioagent.get_agent(res)
        assert isinstance(agent, Agent), agent
        assert agent.name == 'MAPK Signaling Pathway', agent.name
        assert agent.db_refs['TYPE'] == 'ONT::SIGNALING-PATHWAY', agent.db_refs
        assert agent.db_refs['TRIPS'].startswith('V'), agent.db_refs
        assert agent.db_refs['FPLX'] == 'MAPK', agent.db_refs
        assert agent.db_refs['NCIT'], agent.db_refs


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


@raises(SynonymsUnknownError)
def test_get_synonyms_no_synonyms_for_type():
    """raises InvalidAgentError when the agent is not recognized or if the
    input submitted is not valid XML or is not in the correct format
    """
    bs.get_synonyms(Bioagent.get_agent(agent_clj_from_text('vemurafenib')))


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
    assert a1.db_refs['HGNC'] == '6840'
    assert a2.db_refs['UP'] == 'P36507'


def test_respond_get_synonyms():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('GET-SYNONYMS')
    msg_content.set('entity', mek1)
    res = bs.respond_get_synonyms(msg_content)
    assert res.head() == 'SUCCESS'
    syns = res.get('synonyms')
    syn_strs = [s.gets(':name') for s in syns]
    assert 'MAP2K1' in syn_strs
    assert 'MEK1' in syn_strs
    assert 'MKK1' in syn_strs
