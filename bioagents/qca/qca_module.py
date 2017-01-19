import sys
import logging
import json
import xml.etree.ElementTree as ET
from indra.trips.processor import TripsProcessor
from kqml import KQMLModule, KQMLPerformative, KQMLList
from qca import QCA, Disease, \
    DirectedPaths, DiseaseNotFoundException
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
        self.tasks = ['FIND-QCA-PATH', 'HELLO-WORLD']
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
        elif task_str == 'HELLO-WORLD':
            reply_content = self.respond_hello_world('msg', 'content string')
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

    def respond_hello_world(self, msg, content_string):
        print 'Hello world'

        reply_content =\
            KQMLList.from_string(
                '(SUCCESS ' +
                ':speak-message hello_world ')

        return reply_content

    def respond_find_qca_path(self, content_list):
        '''
        Response content to find-qca-path request
        '''

        target_arg = content_list.get_keyword_arg('TARGET')
        targets = []
        source_arg = content_list.get_keyword_arg('SOURCE')
        sources = []
        reltype_arg = content_list.get_keyword_arg('RELTYPE')
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


        #qca = QCA()
        #source_names = ["IRS1"]
        #target_names = ["SHC1"]
        results_list = self.qca.find_causal_path(sources, targets, relation_types=relation_types)

        lispify_helper = Lispify(results_list)


        path_statements = lispify_helper.to_lisp()

        reply_content = KQMLList.from_string(
            '(SUCCESS :paths (' + path_statements + '))')

        return reply_content

    def respond_find_qca_path_local(self, content_list):
        target_arg = content_list.get_keyword_arg('TARGET')
        targets = []
        source_arg = content_list.get_keyword_arg('SOURCE')
        sources = []

        if len(target_arg.data) < 1:
            raise ValueError("Target list is empty")
        else:
            targets = [str(k.data) for k in target_arg.data]

        if len(source_arg.data) < 1:
            raise ValueError("Source list is empty")
        else:
            sources = [str(k.data) for k in source_arg.data]

        directedPaths = DirectedPaths()
        source = ['EGFR']
        target = ['MAP2K1', 'MAP2K2']
        max_number_of_paths = 5
        return_this = []
        with open('RAS_Machine.cx', 'rb') as network_file:
            network = json.load(network_file)
            found_directed_path = dict(data=directedPaths.findDirectedPaths(network, sources, targets, npaths=max_number_of_paths))
            paths_english = found_directed_path.get("data").get("forward_english")

            for path in paths_english:
                path_statement = ""
                for n in path:
                    if type(n) is str:
                        path_statement += n + " "
                    elif type(n) is unicode:
                        path_statement += str(n) + " "
                    elif type(n) is dict:
                        tmp = n.itervalues().next()
                        if "interaction" in tmp:
                            path_statement += tmp.get("interaction") + " "
                        elif "INDRA statement" in tmp:
                            path_statement += tmp.get("INDRA statement") + " "
                        else:
                            path_statement += tmp + " "
                    else:
                        path_statement += " error message: edge missing "
                return_this.append(str(path_statement))

            print return_this

        print 'Here is the input %s' % target_arg

        path_statements = "~ ".join(return_this)

        reply_content = KQMLList.from_string(
            '(SUCCESS :paths (' + path_statements + '))')

        return reply_content

        #reply_msg = KQMLPerformative('reply')
        #reply_msg.set_parameter(':content', reply_content)
        #self.reply(msg, reply_msg)

    def respond_find_qca_path_template(self, content_list):
        '''
        Response content to find-qca-path request
        '''
        disease_arg = content_list.get_keyword_arg(':disease')
        try:
            disease = self.get_disease(disease_arg)
        except Exception as e:
            logger.error(e)
            msg_str = '(FAILURE :reason INVALID_DISEASE)'
            reply_content = KQMLList.from_string(msg_str)
            return reply_content

        if disease.disease_type != 'cancer':
            msg_str = '(FAILURE :reason DISEASE_NOT_FOUND)'
            reply_content = KQMLList.from_string(msg_str)
            return reply_content

        logger.debug('Disease: %s' % disease.name)

        try:
            mut_protein, mut_percent =\
                self.qca.get_top_mutation(disease.name)
        except DiseaseNotFoundException:
            msg_str = '(FAILURE :reason DISEASE_NOT_FOUND)'
            reply_content = KQMLList.from_string(msg_str)
            return reply_content

        # TODO: get functional effect from actual mutations
        # TODO: add list of actual mutations to response
        # TODO: get fraction not percentage from QCA
        reply_content =\
            KQMLList.from_string(
                '(SUCCESS ' +
                ':protein (:name %s :hgnc %s) ' % (mut_protein, mut_protein) +
                ':prevalence %.2f ' % (mut_percent/100.0) +
                ':functional-effect ACTIVE)')

        return reply_content



    def _get_target(self, target_arg):
        target_str = str(target_arg)
        target_str = self.decode_description('<ekb>' + target_str + '</ekb>')
        tp = TripsProcessor(target_str)
        terms = tp.tree.findall('TERM')
        term_id = terms[0].attrib['id']
        agent = tp._get_agent_by_id(term_id, None)
        return agent

    def get_disease(self, disease_arg):
        disease_str = str(disease_arg)
        disease_str = self.decode_description(disease_str)
        term = ET.fromstring(disease_str)
        disease_type = term.find('type').text
        if disease_type.startswith('ONT::'):
            disease_type = disease_type[5:].lower()
        drum_term = term.find('drum-terms/drum-term')
        dbname = drum_term.attrib['name']
        dbid = term.attrib['dbid']
        dbids = dbid.split('|')
        dbid_dict = {k: v for k, v in [d.split(':') for d in dbids]}
        disease = Disease(disease_type, dbname, dbid_dict)
        return disease

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
