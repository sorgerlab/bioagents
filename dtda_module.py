import sys
import operator
from jnius import autoclass, cast
from TripsModule import trips_module

# Declare KQML java classes
KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')

from dtda import DTDA

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
        # TODO: get parameters from content
        drug_arg = cast(KQMLList, content_list.getKeywordArg(':drug'))
        drug = drug_arg.get(0).toString()
        target_arg = cast(KQMLList, content_list.getKeywordArg(':target'))
        target = target_arg.get(0).toString()
        is_target = self.dtda.is_nominal_drug_target(drug, target)
        reply_content = KQMLList()
        status = 'SUCCESS'
        if is_target:
            is_target_str = 'TRUE'
        else:
            is_target_str = 'FALSE'
        msg_str = 'ONT::TELL :status %s :is-target %s' % (status, is_target_str)
        reply_content.add(msg_str)
        return reply_content
    
    def respond_find_target_drug(self, content_list):
        '''
        Response content to find-target-drug request
        '''
        # TODO: implement
        reply_content = KQMLList()
        reply_content.add('')
        return reply_content
    
    def respond_find_disease_targets(self, content_list):
        '''
        Response content to find-disease-targets request
        '''
        # TODO: implement
        self.dtda.get_mutation_statistics('pancreatic', 'missense')
        reply_content = KQMLList()
        reply_content.add('')
        return reply_content

    def respond_find_treatment(self, content_list):
        '''
        Response content to find-treatment request
        '''
        reply_content = KQMLList()
        
        # Parse content
        disease_str = content_list.getKeywordArg(':disease')
        if disease_str is None:
            print 'no disease set'
            return None
        disease_str = disease_str.toString()
        disease_terms = disease_str[1:-1].split(' ')
        disease = disease_terms[0]
        disease_type = disease_terms[1]
        disease_str = disease[3:].lower()

        if disease_str not in ['cancer', 'tumor'] and\
            disease_str.find('carcinoma') == -1 and\
            disease_str.find('cancer') == -1 and\
            disease_str.find('melanoma') == -1:
            print 'problem with disease name'
            return None
        if disease_type == '-':
            disease_type_filter = disease_str
            disease_type_filter = disease_type_filter.replace('cancer', '')
            disease_type_filter = disease_type_filter.replace('-', '')
        else:
            disease_type_filter = disease_type[3:].lower()
       
        print disease_type_filter

        # First, look for possible disease targets
        mutation_stats = self.dtda.get_mutation_statistics(disease_type_filter, 'missense')
        if mutation_stats is None:
            print 'no mutation stats'
            return None

        # Return the top mutation as a possible target
        mutations_sorted = sorted(mutation_stats.items(), 
            key=operator.itemgetter(1), reverse=True)
        top_mutation = mutations_sorted[0]
        mut_protein = top_mutation[0]
        mut_percent = int(top_mutation[1][0]*100.0)
        
        mut_response = KQMLList.fromString('(ONT::TELL :content ' +\
            '(ONT::PROPORTION :refset (ONT::CANCER-PATIENT) ' +\
            ':quan (ONT::PERCENT %d) ' % mut_percent +\
            ':content (ONT::MUTATION :affected ONT::%s)))' % mut_protein)

        # Try to find a drug targeting KRAS
        drugs = self.dtda.find_target_drug(mut_protein)
        #import ipdb; ipdb.set_trace()
        if not drugs:
            drug_response = KQMLList.fromString('(ONT::TELL :content (ONT::DONT-KNOW :content (ONT::A X1 :instance-of ONT::DRUG)))')
        else:
            drugs_str = ', '.join(drugs)
            drug_response = KQMLList.fromString('(ONT::TELL :content (%s))' % drugs_str)
        reply_content.add(KQMLList(mut_response))
        reply_content.add(KQMLList(drug_response))

        return reply_content

if __name__ == "__main__":
    dm = DTDA_Module(['-name', 'DTDA'] + sys.argv[1:])
    dm.run()

