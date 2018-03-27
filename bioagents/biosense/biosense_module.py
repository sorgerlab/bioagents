import os
import sys
import logging
import indra
from indra.util import read_unicode_csv
from indra.tools import expand_families
from indra.sources import trips
from bioagents import Bioagent
from indra.databases import get_identifiers_url
from indra.preassembler.hierarchy_manager import hierarchies
from kqml import KQMLModule, KQMLPerformative, KQMLList, KQMLString


logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('BIOSENSE')


_indra_path = indra.__path__[0]


class BioSense_Module(Bioagent):
    name = 'BioSense'
    tasks = ['CHOOSE-SENSE', 'CHOOSE-SENSE-CATEGORY',
             'CHOOSE-SENSE-IS-MEMBER', 'CHOOSE-SENSE-WHAT-MEMBER']

    def receive_tell(self, msg, content):
        tell_content = content[0].to_string().upper()
        if tell_content == 'START-CONVERSATION':
            logger.info('BioSense resetting')

    def respond_choose_sense(self, content):
        """Return response content to choose-sense request."""
        ekb = content.gets('ekb-term')
        agents, ambiguities = process_ekb(ekb)
        msg = KQMLPerformative('SUCCESS')
        if agents:
            kagents = []
            for term_id, agent_tuple in agents.items():
                kagent = get_kagent(agent_tuple, term_id)
                kagents.append(kagent)
            msg.set('agents', KQMLList(kagents))
        if ambiguities:
            ambiguities_msg = get_ambiguities_msg(ambiguities)
            msg.set('ambiguities', ambiguities_msg)
        return msg

    def respond_choose_sense_category(self, content):
        """Return response content to choose-sense-category request."""
        ekb = content.gets('ekb-term')
        agents, _ = process_ekb(ekb)
        if len(agents) != 1:
            return make_failure('INVALID_AGENT')
        agent = list(agents.values())[0][0]
        category = content.gets('category')
        logger.info("Checking %s for category %s." % (agent, category))
        reg_cat = category.lower().replace('-', ' ')
        if reg_cat in ['kinase', 'kinase activity', 'enzyme']:
            msg = KQMLList('SUCCESS')
            if agent.name in kinase_list:
                msg.set('in-category', 'TRUE')
            else:
                msg.set('in-category', 'FALSE')
        elif reg_cat == 'transcription factor':
            msg = KQMLList('SUCCESS')
            if agent.name in tf_list:
                msg.set('in-category', 'TRUE')
            else:
                msg.set('in-category', 'FALSE')
        else:
            msg = make_failure('UNKNOWN_CATEGORY')
        return msg

    def respond_choose_sense_is_member(self, content):
        """Return response content to choose-sense-is-member request."""
        # Get the member agent first
        ekb = content.gets('ekb-term')
        agents, _ = process_ekb(ekb)
        if len(agents) != 1:
            return make_failure('INVALID_AGENT')
        member_agent = list(agents.values())[0][0]
        # Get the collection next
        ekb = content.gets('collection')
        agents, _ = process_ekb(ekb)
        if len(agents) != 1:
            return make_failure('INVALID_COLLECTION')
        collection_agent = list(agents.values())[0][0]
        if member_agent.isa(collection_agent, hierarchies):
            is_member = 'TRUE'
        else:
            is_member = 'FALSE'
        msg = KQMLList('SUCCESS')
        msg.set('is-member', is_member)
        return msg

    def respond_choose_sense_what_member(self, content):
        """Return response content to choose-sense-what-member request."""
        # Get the collection agent
        ekb = content.gets('collection')
        agents, _ = process_ekb(ekb)
        if len(agents) != 1:
            return make_failure('INVALID_COLLECTION')

        term_id, (agent, ont_type, urls) = list(agents.items())[0]
        members = get_members(agent)
        if members is None:
            return make_failure('COLLECTION_NOT_FAMILY_OR_COMPLEX')

        kagents = [get_kagent((m, 'ONT::PROTEIN', get_urls(m)))
                   for m in members]

        msg = KQMLList('SUCCESS')
        msg.set('members', KQMLList(kagents))
        return msg


def get_kagent(agent_tuple, term_id=None):
    agent, ont_type, urls = agent_tuple
    db_refs = '|'.join('%s:%s' % (k, v) for k, v in
                       agent.db_refs.items())
    kagent = KQMLList(term_id) if term_id else KQMLList()
    kagent.sets('name', agent.name)
    kagent.sets('ids', db_refs)
    url_parts = [KQMLList([':name', KQMLString(k),
                           ':dblink', KQMLString(v)])
                 for k, v in urls.items()]
    url_list = KQMLList()
    for url_part in url_parts:
        url_list.append(url_part)
    kagent.set('id-urls', url_list)
    kagent.set('ont-type', ont_type)
    return kagent


def process_ekb(ekb):
    tp = trips.process_xml(ekb)
    agents = get_agent_tuples(tp)
    ambiguities = get_ambiguities(tp)
    return agents, ambiguities


def get_agent_tuples(tp):
    terms = tp.tree.findall('TERM')
    all_agents = {}
    for term in terms:
        term_id = term.attrib['id']
        _, ont_type, _ = trips.processor._get_db_refs(term)
        agent = tp._get_agent_by_id(term_id, None)
        urls = get_urls(agent)
        all_agents[term_id] = (agent, ont_type, urls)
    return all_agents


def get_urls(agent):
    urls = {k: get_identifiers_url(k, v) for k, v in agent.db_refs.items()
            if k != 'TEXT'}
    return urls


def get_ambiguities(tp):
    terms = tp.tree.findall('TERM')
    all_ambiguities = {}
    for term in terms:
        term_id = term.attrib.get('id')
        _, _, ambiguities = trips.processor._get_db_refs(term)
        if ambiguities:
            all_ambiguities[term_id] = ambiguities
    return all_ambiguities


def get_members(agent):
    dbname, dbid = agent.get_grounding()
    if dbname not in ['FPLX', 'BE']:
        return None
    eh = hierarchies['entity']
    uri = eh.get_uri(dbname, dbid)
    children_uris = sorted(eh.get_children(uri))
    children_agents = [expand_families._agent_from_uri(uri)
                       for uri in children_uris]
    return children_agents


def get_ambiguities_msg(ambiguities):
    sa = []
    for term_id, ambiguity in ambiguities.items():
        msg = KQMLList(term_id)

        pr = ambiguity[0]['preferred']
        pr_dbids = '|'.join([':'.join((k, v)) for
                             k, v in pr['refs'].items()])
        term = KQMLList('term')
        term.set('ont-type', pr['type'])
        term.sets('ids', pr_dbids)
        term.sets('name', pr['name'])
        msg.set('preferred', term)

        alt = ambiguity[0]['alternative']
        alt_dbids = '|'.join([':'.join((k, v)) for
                              k, v in alt['refs'].items()])
        term = KQMLList('term')
        term.set('ont-type', alt['type'])
        term.sets('ids', alt_dbids)
        term.sets('name', alt['name'])
        msg.set('alternative', term)

        sa.append(msg)

    ambiguities_msg = KQMLList(sa)
    return ambiguities_msg


def make_failure(reason):
    msg = KQMLList('FAILURE')
    msg.set('reason', reason)
    return msg


def _read_kinases():
    path = os.path.dirname(os.path.abspath(__file__))
    kinase_table = read_unicode_csv(_indra_path + '/resources/kinases.tsv',
                                    delimiter='\t')
    gene_names = [lin[1] for lin in list(kinase_table)[1:]]
    return gene_names


def _read_tfs():
    path = os.path.dirname(os.path.abspath(__file__))
    tf_table = \
        read_unicode_csv(_indra_path + '/resources/transcription_factors.csv')
    gene_names = [lin[1] for lin in list(tf_table)[1:]]
    return gene_names


kinase_list = _read_kinases()
tf_list = _read_tfs()


if __name__ == "__main__":
    BioSense_Module(argv=sys.argv[1:])
