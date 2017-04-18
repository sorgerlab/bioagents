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
            msg_txt =\
                '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.from_string(msg_txt))
        self.ready()
        super(BioSenseModule, self).start()

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
            content = KQMLPerformative(msg.get_parameter(':content'))
            task_str = content.get_verb()
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
        reply_msg.set_parameter(':content', reply)
        self.reply(msg, reply_msg)

    def respond_choose_sense(self, content):
        """Return response content to build-model request."""
        ekb = _get_model_descr(content, ':ekb-term')
        tp = trips.process_xml(ekb)
        ambiguities = get_ambiguities(tp)
        msg = KQMLPerformative('OK')
        if ambiguities:
            ambiguities_msg = get_ambiguities_msg(ambiguities)
            msg.set_parameter(':ambiguities', ambiguities_msg)
        return msg

def _get_model_descr(content, arg_name):
    descr_arg = content.get_parameter(arg_name)
    descr = descr_arg.to_string()
    if descr[0] == '"':
        descr = descr[1:]
    if descr[-1] == '"':
        descr = descr[:-1]
    descr = descr.replace('\\"', '"')
    return descr

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
        pr = ambiguity[0]['preferred']
        pr_dbids = '|'.join(['::'.join((k, v)) for
                             k, v in pr['refs'].items()])
        # TODO: once available, replace with real ont type
        pr_type = 'ONT::PROTEIN'
        s1 = '(term :ont-type %s :ids "%s" :name "%s")' % \
            (pr_type, pr_dbids, pr['name'])
        alt = ambiguity[0]['alternative']
        alt_dbids = '|'.join(['::'.join((k, v)) for
                              k, v in alt['refs'].items()])
        # TODO: once available, replace with real ont type
        alt_type = 'ONT::PROTEIN-FAMILY'
        s2 = '(term :ont-type %s :ids "%s" :name "%s")' % \
            (alt_type, alt_dbids, alt['name'])
        s = '(%s :preferred %s :alternative %s)' % \
            (term_id, s1, s2)
        sa.append(s)
    ambiguities_msg = KQMLList.from_string('(' + ' '.join(sa) + ')')
    return ambiguities_msg


if __name__ == "__main__":
    BioSenseModule(['-name', 'BIOSENSE'] + sys.argv[1:])
