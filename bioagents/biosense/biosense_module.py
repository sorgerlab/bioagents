import os
import sys
import logging
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('BIOSENSE')
import indra
from indra.util import read_unicode_csv
from indra.sources import trips
from bioagents import Bioagent
from indra.databases import get_identifiers_url
from indra.preassembler.hierarchy_manager import hierarchies
from kqml import KQMLModule, KQMLPerformative, KQMLList, KQMLString

_indra_path = indra.__path__[0]

class BioSense_Module(Bioagent):
    name = 'BioSense'
    tasks = ['CHOOSE-SENSE']
    def receive_tell(self, msg, content):
        tell_content = content[0].to_string().upper()
        if tell_content == 'START-CONVERSATION':
            logger.info('BioSense resetting')

    def receive_request(self, msg, content):
        """Handle request messages and respond.

        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        message is then sent back.
        """
        content = msg.get('content')
        task_str = content.head().upper()
        if task_str not in self.tasks:
            self.error_reply(msg, 'Unknown task ' + task_str)
            return
        try:
            task_str = task_str.replace('-','_').lower()
            fun_name = 'respond_%s' % task_str
            fun = getattr(self, fun_name)
            reply = fun(content)
        except Exception as e:
            logger.error('Failed to perform task.')
            logger.error(e)
            reply = KQMLList.from_string('(FAILURE INTERNAL_ERROR)')

        return self.reply_with_content(msg, reply_content)

    def respond_choose_sense(self, content):
        """Return response content to choose-sense request."""
        ekb = content.gets('ekb-term')
        tp = trips.process_xml(ekb)
        agents = get_agents(tp)
        ambiguities = get_ambiguities(tp)
        msg = KQMLPerformative('OK')
        if agents:
            kagents = []
            for term_id, agent_tuple in agents.items():
                agent, ont_type, urls = agent_tuple
                db_refs = '|'.join('%s:%s' % (k, v) for k, v in
                                   agent.db_refs.items())
                name = agent.name
                kagent = KQMLList(term_id)
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
                kagents.append(kagent)
            msg.set('agents', KQMLList(kagents))
        if ambiguities:
            ambiguities_msg = get_ambiguities_msg(ambiguities)
            msg.set('ambiguities', ambiguities_msg)
        return msg

    def respond_choose_sense_category(self, content):
        """Return response content to choose-sense-category request."""
        ekb = content.gets('ekb-term')
        tp = trips.process_xml(ekb)
        agent_dict = get_agents(tp)
        if len(agent_dict) != 1:
            return make_failure('INVALID_AGENT')
        agent = list(agent_dict.values())[0][0]
        category = content.gets('category')
        if category == 'kinase activity':
            msg = KQMLList('SUCCESS')
            if agent.name in kinase_list:
                msg.set('in-category', 'TRUE')
            else:
                msg.set('in-category', 'FALSE')
        elif category == 'transcription factor':
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
        tp = trips.process_xml(ekb)
        agent_dict = get_agents(tp)
        if len(agent_dict) != 1:
            return make_failure('INVALID_AGENT')
        member_agent = list(agent_dict.values())[0][0]
        # Get the collection next
        ekb = content.gets('collection')
        tp = trips.process_xml(ekb)
        agent_dict = get_agents(tp)
        if len(agent_dict) != 1:
            return make_failure('INVALID_AGENT')
        collection_agent = list(agent_dict.values())[0][0]
        if member_agent.isa(collection_agent, hierarchies):
            is_member = 'TRUE'
        else:
            is_member = 'FALSE'
        msg = KQMLList('SUCCESS')
        msg.set('is-member', is_member)
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

def get_agents(tp):
    terms = tp.tree.findall('TERM')
    all_agents = {}
    for term in terms:
        term_id = term.attrib['id']
        _, ont_type, _ = trips.processor._get_db_refs(term)
        agent = tp._get_agent_by_id(term_id, None)
        urls = {k: get_identifiers_url(k, v) for k, v in agent.db_refs.items()
                if k != 'TEXT'}
        all_agents[term_id] = (agent, ont_type, urls)
    return all_agents

def get_ambiguities(tp):
    terms = tp.tree.findall('TERM')
    all_ambiguities = {}
    for term in terms:
        term_id = term.attrib.get('id')
        _, _, ambiguities = trips.processor._get_db_refs(term)
        if ambiguities:
            all_ambiguities[term_id] = ambiguities
    return all_ambiguities

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


if __name__ == "__main__":
    BioSense_Module(argv=sys.argv[1:])
