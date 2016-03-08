import sys
from jnius import autoclass, cast
from TripsModule import trips_module

# Declare KQML java classes
KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')

from dtda import DTDA, DrugNotFoundException, DiseaseNotFoundException

# TODO: standardize dash/underscore

class DTDA_Module(trips_module.TripsModule):
    '''
    The DTDA module is a TRIPS module built around the DTDA agent. Its role is to
    receive and decode messages and send responses from and to other agents in 
    the system.
    '''
    def __init__(self, argv):
        # Call the constructor of TripsModule
        super(DTDA_Module, self).__init__(argv)
        self.tasks = ['IS-DRUG-TARGET', 'FIND-TARGET-DRUG', 
                      'FIND-DISEASE-TARGETS', 'FIND-TREATMENT']

    def init(self):
        '''
        Initialize TRIPS module
        '''
        super(DTDA_Module, self).init()
        # Send subscribe messages
        for task in self.tasks:
            msg_txt = '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.fromString(msg_txt))
        # Instantiate a singleton DTDA agent
        self.dtda = DTDA()
        # Send ready message
        self.ready()

    def receive_request(self, msg, content):
        '''
        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply 
        "tell" message is then sent back.
        '''
        content_list = cast(KQMLList, content)
        task_str = content_list.get(0).toString().upper()
        if task_str == 'IS-DRUG-TARGET':
            reply_content = self.respond_is_drug_target(content_list)
        elif task_str == 'FIND-TARGET-DRUG':
            reply_content = self.respond_find_target_drug(content_list)
        elif task_str == 'FIND-DISEASE-TARGETS':
            reply_content = self.respond_find_disease_targets(content_list)
        elif task_str == 'FIND-TREATMENT':
            reply_content = self.respond_find_treatment(content_list)
            if reply_content is None:
                self.respond_dont_know(msg, '(ONT::A X1 :instance-of ONT::DRUG)')
                return
        else:
            self.error_reply(msg, 'unknown request task ' + task_str)
            return
        
        reply_msg = KQMLPerformative('reply')
        reply_msg.setParameter(':content', cast(KQMLObject, reply_content))
        self.reply(msg, reply_msg)
   
    def respond_dont_know(self, msg, content_string):
        resp = '(ONT::TELL :content (ONT::DONT-KNOW :content %s))' % content_string
        resp_list = KQMLList.fromString(resp)
        reply_msg = KQMLPerformative('reply')
        reply_msg.setParameter(':content', cast(KQMLObject, resp_list))
        self.reply(msg, reply_msg)

    def respond_is_drug_target(self, content_list):
        '''
        Response content to is-drug-target request
        '''
        drug_arg = cast(KQMLList, content_list.getKeywordArg(':drug'))
        drug = drug_arg.get(0).toString()
        target_arg = cast(KQMLList, content_list.getKeywordArg(':target'))
        target = target_arg.get(0).toString()
        reply_content = KQMLList()
        try:
            is_target = self.dtda.is_nominal_drug_target(drug, target)
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
        # TODO: implement
        target = content_list.getKeywordArg(':target')
        target_str = target.toString()[1:-1]
        drug_names, chebi_ids = self.dtda.find_target_drugs(target_str)
        drug_list_str = ''
        for dn, ci in zip(drug_names, chebi_ids):
            if ci is None:
                drug_list_str += '(:name %s) ' % dn.encode('ascii', 'ignore')
            else:
                drug_list_str += '(:name %s :chebi_id %s) ' % (dn, ci)
        reply_content = KQMLList.fromString(
            '(SUCCESS :drugs (' + drug_list_str + '))')
        return reply_content
    
    def respond_find_disease_targets(self, content_list):
        '''
        Response content to find-disease-targets request
        '''
        disease_str = content_list.getKeywordArg(':disease')
        try:
            disease_type_filter = self.get_disease_filter(disease_str)
        except DiseaseNotFoundException:
            reply_content = KQMLList.fromString(
                '(FAILURE :reason DISEASE_NOT_FOUND)')
            return reply_content  
        print disease_type_filter

        mut_protein, mut_percent = self.dtda.get_top_mutation(disease_type_filter)

        # TODO: get functional effect from actual mutations
        # TODO: add list of actual mutations to response
        # TODO: get fraction not percentage from DTDA
        reply_content =\
            KQMLList.fromString(
                '(SUCCESS ' +\
                ':protein (:name %s :hgnc %s) ' % (mut_protein, mut_protein) +\
                ':prevalence %.2f ' % (mut_percent/100.0) +\
                ':functional-effect ACTIVE)')

        return reply_content

    def respond_find_treatment(self, content_list):
        '''
        Response content to find-treatment request
        ''' 
        #TODO: eliminate code duplication here
        disease_str = content_list.getKeywordArg(':disease')
        reply_content = KQMLList()
        try:
            disease_type_filter = self.get_disease_filter(disease_str)
        except DiseaseNotFoundException:
            reply_content.add('FAILURE :reason DISEASE_NOT_FOUND')
            return reply_content 
        print disease_type_filter

        mut_protein, mut_percent = self.dtda.get_top_mutation(disease_type_filter)

        # TODO: get functional effect from actual mutations
        # TODO: add list of actual mutations to response
        # TODO: get fraction not percentage from DTDA
        reply_content.add(KQMLList.fromString(
                '(SUCCESS ' +\
                ':protein (:name %s :hgnc %s) ' % (mut_protein, mut_protein) +\
                ':prevalence %.2f ' % (mut_percent/100.0) +\
                ':functional-effect ACTIVE)'))

        # Try to find a drug
        drug_names, chebi_ids = self.dtda.find_target_drugs(mut_protein)
        drug_list_str = ''
        for dn, ci in zip(drug_names, chebi_ids):
            if ci is None:
                drug_list_str += '(:name %s) ' % dn.encode('ascii', 'ignore')
            else:
                drug_list_str += '(:name %s :chebi_id %s) ' % (dn, ci)
        reply_content.add(KQMLList.fromString(
            '(SUCCESS :drugs (' + drug_list_str + '))'))
        
        return reply_content

    @staticmethod
    def get_disease_filter(disease_str):
        if disease_str is None:
            print 'no disease set'
            raise DiseaseNotFoundException
        disease_str = disease_str.toString()
        disease_terms = disease_str[1:-1].split('-')
        disease_str = disease_terms[1].lower()

        if disease_str not in ['cancer', 'tumor'] and\
            disease_str.find('carcinoma') == -1 and\
            disease_str.find('cancer') == -1 and\
            disease_str.find('melanoma') == -1:
            print 'problem with disease name'
            raise DiseaseNotFoundException
        disease_type_filter = disease_terms[0].lower()
        return disease_type_filter

if __name__ == "__main__":
    dm = DTDA_Module(['-name', 'DTDA'] + sys.argv[1:])
    dm.run()

