import sys
import logging
import json
import xml.etree.ElementTree as ET
from indra.trips.processor import TripsProcessor
from kqml import KQMLModule, KQMLPerformative, KQMLList
from qca import QCA
from lispify_helper import Lispify

logger = logging.getLogger('QCA')

# TODO: standardize dash/underscore
class QCA_Module(KQMLModule):
    '''
    The QCA module is a TRIPS module built around the QCA agent.
    Its role is to receive and decode messages and send responses from and
    to other agents in the system.
    '''
    def __init__(self, argv):
        # Call the constructor of TripsModule
        super(QCA_Module, self).__init__(argv)
        self.tasks = ['FIND-QCA-PATH', 'HAS-QCA-PATH']
        # Send subscribe messages
        for task in self.tasks:
            msg_txt =\
                '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.from_string(msg_txt))
        # Instantiate a singleton QCA agent
        self.qca = QCA()
        # Send ready message
        self.ready()
        super(QCA_Module, self).start()

    def receive_request(self, msg, content):
        '''
        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        message is then sent back.
        '''
        content_list = content
        task_str = content_list[0].to_string().upper()
        if task_str == 'FIND-QCA-PATH':
            reply_content = self.respond_find_qca_path(content_list)
        elif task_str == 'HAS-QCA-PATH':
            reply_content = self.has_qca_path(content_list)
        else:
            self.error_reply(msg, 'unknown request task ' + task_str)
            return

        reply_msg = KQMLPerformative('reply')
        reply_msg.set_parameter(':content', reply_content)
        self.reply(msg, reply_msg)

    def respond_dont_know(self, msg, content_string):
        resp = '(ONT::TELL :content (ONT::DONT-KNOW :content %s))' %\
            content_string
        resp_list = KQMLList.from_string(resp)
        reply_msg = KQMLPerformative('reply')
        reply_msg.set_parameter(':content', resp_list)
        self.reply(msg, reply_msg)

    def respond_find_qca_path(self, content_list):
        '''
        Response content to find-qca-path request
        '''

        target_arg = content_list.get_keyword_arg(':TARGET')
        targets = []
        source_arg = content_list.get_keyword_arg(':SOURCE')
        sources = []
        reltype_arg = content_list.get_keyword_arg(':RELTYPE')
        relation_types = []

        if len(target_arg.data) < 1:
            raise ValueError("Target list is empty")
        else:
            targets = [str(k.data) for k in target_arg.data]

        if len(source_arg.data) < 1:
            raise ValueError("Source list is empty")
        else:
            sources = [str(k.data) for k in source_arg.data]

        if reltype_arg is None or len(reltype_arg.data) < 1:
            relation_types = None
        else:
            relation_types = [str(k.data) for k in reltype_arg.data]

        results_list = self.qca.find_causal_path(sources, targets, relation_types=relation_types)

        lispify_helper = Lispify(results_list)

        path_statements = lispify_helper.to_lisp()

        reply_content = KQMLList.from_string(
            '(SUCCESS :paths (' + path_statements + '))')

        return reply_content

    def has_qca_path(self, content_list):
        '''
        Response content to find-qca-path request
        '''

        target_arg = content_list.get_keyword_arg(':TARGET')
        targets = []
        source_arg = content_list.get_keyword_arg(':SOURCE')
        sources = []
        reltype_arg = content_list.get_keyword_arg(':RELTYPE')
        relation_types = []

        if len(target_arg.data) < 1:
            raise ValueError("Target list is empty")
        else:
            targets = [str(k.data) for k in target_arg.data]

        if len(source_arg.data) < 1:
            raise ValueError("Source list is empty")
        else:
            sources = [str(k.data) for k in source_arg.data]

        if reltype_arg is None or len(reltype_arg.data) < 1:
            relation_types = None
        else:
            relation_types = [str(k.data) for k in reltype_arg.data]

        has_path = self.qca.has_path(sources, targets)

        reply_content = KQMLList.from_string(
            '(SUCCESS :haspath (' + str(has_path) + '))')

        return reply_content

    def _get_target(self, target_arg):
        target_str = str(target_arg)
        target_str = self.decode_description('<ekb>' + target_str + '</ekb>')
        tp = TripsProcessor(target_str)
        terms = tp.tree.findall('TERM')
        term_id = terms[0].attrib['id']
        agent = tp._get_agent_by_id(term_id, None)
        return agent

    @staticmethod
    def get_single_argument(arg):
        if arg is None:
            return None
        arg_str = arg.to_string()
        if arg_str[0] == '(' and arg_str[-1] == ')':
             arg_str = arg_str[1:-1]
        arg_str = arg_str.lower()
        return arg_str

    @staticmethod
    def decode_description(descr):
        if descr[0] == '"':
            descr = descr[1:]
        if descr[-1] == '"':
            descr = descr[:-1]
        descr = descr.replace('\\"', '"')
        return descr

if __name__ == "__main__":
    QCA_Module(['-name', 'QCA'] + sys.argv[1:])
