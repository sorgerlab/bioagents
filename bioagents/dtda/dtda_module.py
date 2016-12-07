import sys
import logging
import xml.etree.ElementTree as ET
from indra.trips.processor import TripsProcessor
from kqml import KQMLModule, KQMLPerformative, KQMLList
from dtda import DTDA, Disease, \
                 DrugNotFoundException, DiseaseNotFoundException

logger = logging.getLogger('DTDA')

# TODO: standardize dash/underscore
class DTDA_Module(KQMLModule):
    '''
    The DTDA module is a TRIPS module built around the DTDA agent.
    Its role is to receive and decode messages and send responses from and
    to other agents in the system.
    '''
    def __init__(self, argv):
        # Call the constructor of TripsModule
        super(DTDA_Module, self).__init__(argv)
        self.tasks = ['IS-DRUG-TARGET', 'FIND-TARGET-DRUG',
                      'FIND-DISEASE-TARGETS', 'FIND-TREATMENT']
        # Send subscribe messages
        for task in self.tasks:
            msg_txt =\
                '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.from_string(msg_txt))
        # Instantiate a singleton DTDA agent
        self.dtda = DTDA()
        # Send ready message
        self.ready()
        super(DTDA_Module, self).start()

    def receive_request(self, msg, content):
        '''
        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        message is then sent back.
        '''
        content_list = content
        task_str = content_list[0].to_string().upper()
        if task_str == 'IS-DRUG-TARGET':
            reply_content = self.respond_is_drug_target(content_list)
        elif task_str == 'FIND-TARGET-DRUG':
            reply_content = self.respond_find_target_drug(content_list)
        elif task_str == 'FIND-DISEASE-TARGETS':
            reply_content = self.respond_find_disease_targets(content_list)
        elif task_str == 'FIND-TREATMENT':
            reply_content = self.respond_find_treatment(content_list)
            if reply_content is None:
                self.respond_dont_know(msg,
                                       '(ONT::A X1 :instance-of ONT::DRUG)')
                return
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

    def respond_is_drug_target(self, content_list):
        '''
        Response content to is-drug-target request
        '''
        drug_arg = content_list.get_keyword_arg(':drug')
        drug = drug_arg[0].to_string()
        target_arg = content_list.get_keyword_arg(':target')
        target = self._get_target(target_arg)
        target_name = target.name
        reply_content = KQMLList()
        try:
            is_target = self.dtda.is_nominal_drug_target(drug, target_name)
        except DrugNotFoundException:
            reply_content.add('FAILURE :reason DRUG_NOT_FOUND')
            return reply_content
        status = 'SUCCESS'
        if is_target:
            is_target_str = 'TRUE'
        else:
            is_target_str = 'FALSE'
        msg_str = '%s :is-target %s' %\
                  (status, is_target_str)
        reply_content.add(msg_str)
        return reply_content

    def respond_find_target_drug(self, content_list):
        '''
        Response content to find-target-drug request
        '''
        target_arg = content_list.get_keyword_arg(':target')
        target = self._get_target(target_arg)
        target_name = target.name
        drug_names, chebi_ids = self.dtda.find_target_drugs(target_name)
        drug_list_str = ''
        for dn, ci in zip(drug_names, chebi_ids):
            if ci is None:
                drug_list_str += '(:name %s) ' % dn.encode('ascii', 'ignore')
            else:
                drug_list_str += '(:name %s :chebi_id %s) ' % (dn, ci)
        reply_content = KQMLList.from_string(
            '(SUCCESS :drugs (' + drug_list_str + '))')
        return reply_content

    def respond_find_disease_targets(self, content_list):
        '''
        Response content to find-disease-targets request
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
                self.dtda.get_top_mutation(disease.name)
        except DiseaseNotFoundException:
            msg_str = '(FAILURE :reason DISEASE_NOT_FOUND)'
            reply_content = KQMLList.from_string(msg_str)
            return reply_content

        # TODO: get functional effect from actual mutations
        # TODO: add list of actual mutations to response
        # TODO: get fraction not percentage from DTDA
        reply_content =\
            KQMLList.from_string(
                '(SUCCESS ' +
                ':protein (:name %s :hgnc %s) ' % (mut_protein, mut_protein) +
                ':prevalence %.2f ' % (mut_percent/100.0) +
                ':functional-effect ACTIVE)')

        return reply_content

    def respond_find_treatment(self, content_list):
        '''
        Response content to find-treatment request
        '''
        reply_content = KQMLList()
        #TODO: eliminate code duplication here
        disease_arg = content_list.get_keyword_arg(':disease')
        try:
            disease = self.get_disease(disease_arg)
        except Exception as e:
            logger.error(e)
            msg_str = '(FAILURE :reason INVALID_DISEASE)'
            reply_content = KQMLList.from_string(msg_str)
            return reply_content

        if disease.disease_type != 'cancer':
            reply_content.add('FAILURE :reason DISEASE_NOT_FOUND')
            return reply_content

        logger.debug('Disease: %s' % disease.name)

        try:
            mut_protein, mut_percent = \
                self.dtda.get_top_mutation(disease.name)
        except DiseaseNotFoundException:
            reply_content.add('FAILURE :reason DISEASE_NOT_FOUND')
            return reply_content

        # TODO: get functional effect from actual mutations
        # TODO: add list of actual mutations to response
        # TODO: get fraction not percentage from DTDA
        reply_content.add(KQMLList.from_string(
                '(SUCCESS ' +
                ':protein (:name %s :hgnc %s) ' % (mut_protein, mut_protein) +
                ':prevalence %.2f ' % (mut_percent/100.0) +
                ':functional-effect ACTIVE)'))

        # Try to find a drug
        drug_names, chebi_ids = self.dtda.find_target_drugs(mut_protein)
        drug_list_str = ''
        for dn, ci in zip(drug_names, chebi_ids):
            if ci is None:
                drug_list_str += '(:name %s) ' % dn.encode('ascii', 'ignore')
            else:
                drug_list_str += '(:name %s :chebi_id %s) ' % (dn, ci)
        reply_content.add(KQMLList.from_string(
            '(SUCCESS :drugs (' + drug_list_str + '))'))

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
    DTDA_Module(['-name', 'DTDA'] + sys.argv[1:])
