import sys
import json
import logging
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('QCA')
import xml.etree.ElementTree as ET
from indra.trips.processor import TripsProcessor
from kqml import KQMLModule, KQMLPerformative, KQMLList, KQMLString, KQMLToken
from qca import QCA


class QCA_Module(KQMLModule):
    '''
    The QCA module is a TRIPS module built around the QCA agent.
    Its role is to receive and decode messages and send responses from and
    to other agents in the system.
    '''
    def __init__(self, argv, testing=False):
        # Instantiate a singleton QCA agent
        self.qca = QCA()
        if testing:
            return
        # Call the constructor of TripsModule
        super(QCA_Module, self).__init__(argv)
        self.tasks = ['FIND-QCA-PATH', 'HAS-QCA-PATH']
        # Send subscribe messages
        for task in self.tasks:
            msg_txt =\
                '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.from_string(msg_txt))
        # Send ready message
        self.ready()
        super(QCA_Module, self).start()

    def receive_request(self, msg, content):
        """Handle request messages and respond.

        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        message is then sent back.
        """
        content = msg.get('content')
        task_str = content.head().upper()
        if task_str == 'FIND-QCA-PATH':
            try:
                reply_content = self.respond_find_qca_path(content)
            except Exception as e:
                logger.error(e)
                reply_content = KQMLList.from_string('(FAILURE)')
        elif task_str == 'HAS-QCA-PATH':
            try:
                reply_content = self.has_qca_path(content)
            except Exception as e:
                logger.error(e)
                reply_content = KQMLList.from_string('(FAILURE)')
        else:
            reply_content = KQMLList.from_string('(FAILURE)')

        reply_msg = KQMLPerformative('reply')
        reply_msg.set('content', reply_content)
        self.reply(msg, reply_msg)

    def respond_dont_know(self, msg, content_string):
        resp = '(ONT::TELL :content (ONT::DONT-KNOW :content %s))' %\
            content_string
        resp_list = KQMLList.from_string(resp)
        reply_msg = KQMLPerformative('reply')
        reply_msg.set('content', resp_list)
        self.reply(msg, reply_msg)

    def respond_find_qca_path(self, content):
        """Response content to find-qca-path request"""
        source_arg = content.gets('SOURCE')
        target_arg = content.gets('TARGET')
        reltype_arg = content.get('RELTYPE')

        if not source_arg:
            raise ValueError("Source list is empty")
        if not target_arg:
            raise ValueError("Target list is empty")

        target = self._get_term_name(target_arg)
        source = self._get_term_name(source_arg)

        if reltype_arg is None or len(reltype_arg) == 0:
            relation_types = None
        else:
            relation_types = [str(k.data) for k in reltype_arg.data]

        results_list = self.qca.find_causal_path([source], [target],
                                                 relation_types=relation_types)
        if not results_list:
            reply_content = KQMLList.from_string('(FAILURE NO_PATH_FOUND)')
            return reply_content
        first_result = results_list[0]
        first_edges = first_result[1::2]
        indra_edges = [fe[0]['INDRA json'] for fe in first_edges]
        indra_edges = [json.loads(e) for e in indra_edges]
        indra_edges_str = json.dumps(indra_edges)
        ks = KQMLString(indra_edges_str)

        reply_content = KQMLList(['SUCCESS', ':paths', KQMLList([ks])])

        return reply_content

    def has_qca_path(self, content):
        """Response content to find-qca-path request."""
        target_arg = content.gets('TARGET')
        source_arg = content.gets('SOURCE')
        reltype_arg = content.get('RELTYPE')
        relation_types = []

        if not source_arg:
            raise ValueError("Source list is empty")
        if not target_arg:
            raise ValueError("Target list is empty")

        target = self._get_term_name(target_arg)
        source = self._get_term_name(source_arg)

        if reltype_arg is None or len(reltype_arg) == 0:
            relation_types = None
        else:
            relation_types = [str(k.data) for k in reltype_arg.data]

        has_path = self.qca.has_path([source], [target])

        reply_content = KQMLList.from_string(
            '(SUCCESS :haspath (' + str(has_path) + '))')

        return reply_content

    def _get_term_name(self, term_str):
        term_str = '<ekb>' + term_str + '</ekb>'
        tp = TripsProcessor(term_str)
        terms = tp.tree.findall('TERM')
        term_id = terms[0].attrib['id']
        agent = tp._get_agent_by_id(term_id, None)
        return agent.name

if __name__ == "__main__":
    QCA_Module(['-name', 'QCA'] + sys.argv[1:])
