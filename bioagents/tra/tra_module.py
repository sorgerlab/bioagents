import sys
import argparse
import logging

from indra.trips import processor as trips_processor
from pysb import bng, Initial, Parameter, ComponentDuplicateNameError

from bioagents.tra.tra import *
from bioagents.trips import trips_module
from bioagents.trips.kqml_list import KQMLList
from bioagents.trips.kqml_performative import KQMLPerformative

logger = logging.getLogger('TRA')

class TRA_Module(trips_module.TripsModule):
    def __init__(self, argv):
        super(TRA_Module, self).__init__(argv)
        self.tasks = ['SATISFIES-PATTERN']

    def init(self):
        '''
        Initialize TRIPS module
        '''
        super(TRA_Module, self).init()
        # Send subscribe messages
        for task in self.tasks:
            msg_txt =\
                '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.from_string(msg_txt))
        # Instantiate a singleton TRA agent
        self.tra = TRA()
        self.ready()

    def receive_request(self, msg, content):
        '''
        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        "tell" message is then sent back.
        '''
        content_list = content
        task_str = content_list[0].to_string().upper()
        if task_str == 'SATISFIES-PATTERN':
            try:
                reply_content = self.respond_satisfies_pattern(content_list)
            except Exception as e:
                self.error_reply(msg, 'Error in performing satisfies ' +
                                      'pattern task.')
                return
        else:
            self.error_reply(msg, 'Unknown request task ' + task_str)
            return

        reply_msg = KQMLPerformative('reply')
        reply_msg.set_parameter(':content', reply_content)
        self.reply(msg, reply_msg)

    def respond_satisfies_pattern(self, content_list):
        '''
        Response content to satisfies-pattern request
        '''
        pattern_lst = content_list.get_keyword_arg(':pattern')
        conditions_lst = content_list.get_keyword_arg('conditions')

        try:
            pattern = self.get_temporal_pattern(pattern_lst)
        except Exception as e:
            logger.error(e)
            reply_content =\
                KQMLList.from_string('(FAILURE :reason INVALID_PATTERN)')
            return reply_content
        try:
            for condition_lst in conditions_lst:
                conditions_lst = self.get_molecular_condition(condition_lst)
        except Exception as e:
            logger.error(e)
            reply_content =\
                KQMLList.from_string('(FAILURE :reason INVALID_CONDITIONS)')
            return reply_content

        reply_content = KQMLList()
        reply_content.add('SUCCESS :content (:target_match %s)' %
                          target_match_str)
        return reply_content

def get_molecular_entity(lst):
    try:
        description = lst.get_keyword_arg(':description')
        tp = trips_processor.TripsProcessor(description)
        # Get Agent from TERM
    except Exception as e:
        raise InvalidMolecularEntityError
    return

def get_molecular_quantity(lst):
    quant_type = lst.get_keyword_arg(':type')
    value = lst.get_keyword_arg(':value')
    return MolecularQuantity(quant_type, value)

def get_molecular_quantity_ref(lst):
    quant_type = lst.get_keyword_arg(':type')
    entity = get_molecular_entity(lst)
    return MolecularQuantityRef(quant_type, entity)

def get_time_interval(lst):
    lb = lst.get_keyword_arg(':lower-bound')
    ub = lst.get_keyword_arg(':upper-bound')
    unit = lst.get_keyword_arg(':unit')
    return TimeInterval(lb, ub, unit)

def get_temporal_pattern(lst):
    pattern_type = lst.get_keyword_arg(':type')
    pass

def get_molecular_condition(lst):
    condition_type = lst.get_keyword_arg(':type')
    quantity_ref_lst = lst.get_keyword_arg(':quantity')
    quantity = get_molecular_quantity_ref(lst)
    value = lst.get_keyword_arg(':value')
    mc = MolecularCondition(condition_type, quantity, value)
    return mc

if __name__ == "__main__":
    m = TRA_Module(['-name', 'TRA'] + sys.argv[1:])
    m.start()
    m.join()
