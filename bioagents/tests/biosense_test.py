import unittest
from kqml import KQMLList
from .util import ekb_from_text
from bioagents.biosense.biosense_module import BioSense_Module

mek1_ekb = ekb_from_text('MAP2K1')
mek_ekb = ekb_from_text('MEK')

# BioSense module unit tests


def test_choose_sense():
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


def test_choose_nonsense():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('CHOOSE-SENSE')
    msg_content.sets('ekb-term', ekb_from_text('bagel'))
    res = bs.respond_choose_sense(msg_content)
    print(res)
    assert res.head() == 'SUCCESS'
    assert res.get('agents')[0].gets('ont-type') == None


@unittest.skip('No ambiguity reported here yet')
def test_choose_sense_ambiguity():
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


def test_choose_sense_category():
    bs = BioSense_Module(testing=True)
    msg_content = KQMLList('CHOOSE-SENSE-CATEGORY')
    msg_content.sets('ekb-term', mek1_ekb)
    for cat in ['kinase activity', 'enzyme']:
        msg_content.sets('category', cat)
        res = bs.respond_choose_sense_category(msg_content)
        print(res)
        print(res.head())
        assert(res.head() == 'SUCCESS')
        assert(res.get('in-category') == 'TRUE')
    msg_content = KQMLList('CHOOSE-SENSE-CATEGORY')
    msg_content.sets('ekb-term', ekb_from_text('BRAF'))
    msg_content.sets('category', 'kinase')
    res = bs.respond_choose_sense_category(msg_content)
    print(res)
    assert res.head() == 'SUCCESS'


def test_choose_sense_is_member():
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

def test_choose_sense_what_member():
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

