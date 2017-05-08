import sys
import json
import logging
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('BIOSENSE')
from indra import trips
from kqml import *


class BioSenseModule(KQMLModule):
    def __init__(self, argv):
        super(BioSenseModule, self).__init__(argv)
        self.tasks = ['CHOOSE-SENSE']
        for task in self.tasks:
            self.subscribe_request(task)
        self.ready()
        self.start()

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
        try:
            content = msg.get('content')
            task_str = content.head().upper()
        except Exception as e:
            logger.error('Could not get task string from request.')
            logger.error(e)
            self.error_reply(msg, 'Invalid task')
        #try:
        if task_str == 'CHOOSE-SENSE':
            reply = self.respond_choose_sense(content)
        else:
            self.error_reply(msg, 'Unknown task ' + task_str)
            return
        #except Exception as e:
        #    logger.error('Failed to perform task.')
        #    logger.error(e)
        #    reply = KQMLList.from_string('(FAILURE INTERNAL_ERROR)')

        reply_msg = KQMLPerformative('reply')
        reply_msg.set('content', reply)
        self.reply(msg, reply_msg)

    def respond_choose_sense(self, content):
        """Return response content to build-model request."""
        ekb = content.gets('ekb-term')
        tp = trips.process_xml(ekb)
        ambiguities = get_ambiguities(tp)
        msg = KQMLPerformative('OK')
        if ambiguities:
            ambiguities_msg = get_ambiguities_msg(ambiguities)
            msg.set('ambiguities', ambiguities_msg)
        return msg

def get_ambiguities(tp):
    terms = tp.tree.findall('TERM')
    all_ambiguities = {}
    for term in terms:
        term_id = term.attrib.get('id')
        _, ambiguities = trips.processor._get_db_refs(term)
        if ambiguities:
            all_ambiguities[term_id] = ambiguities
    return all_ambiguities

def get_ambiguities_msg(ambiguities):
    sa = []
    for term_id, ambiguity in ambiguities.items():
        msg = KQMLList(term_id)

        pr = ambiguity[0]['preferred']
        pr_dbids = '|'.join(['::'.join((k, v)) for
                             k, v in pr['refs'].items()])
        # TODO: once available, replace with real ont type
        pr_type = 'ONT::PROTEIN'
        term = KQMLList('term')
        term.set('ont-type', pr_type)
        term.sets('ids', pr_dbids)
        term.sets('name', pr['name'])
        msg.set('preferred', term)

        # TODO: once available, replace with real ont type
        alt_type = 'ONT::PROTEIN-FAMILY'
        alt = ambiguity[0]['alternative']
        alt_dbids = '|'.join(['::'.join((k, v)) for
                              k, v in alt['refs'].items()])
        term = KQMLList('term')
        term.set('ont-type', alt_type)
        term.sets('ids', alt_dbids)
        term.sets('name', alt['name'])
        msg.set('alternative', term)

        sa.append(msg)

    ambiguities_msg = KQMLList(sa)
    return ambiguities_msg


if __name__ == "__main__":
    BioSenseModule(['-name', 'BIOSENSE'] + sys.argv[1:])
