import sys
import argparse
import logging
import tempfile

from indra import trips
from indra.assemblers import PysbAssembler
from indra.trips import processor as trips_processor
from pysb import bng, Initial, Parameter, ComponentDuplicateNameError, \
                 SelfExporter

from bioagents.tra.tra import *
from bioagents.kappa import kappa_client
from bioagents.trips import trips_module
from bioagents.trips.kqml_list import KQMLList
from bioagents.trips.kqml_performative import KQMLPerformative

logger = logging.getLogger('TRA')

class TRA_Module(trips_module.TripsModule):
    def __init__(self, argv):
        super(TRA_Module, self).__init__(argv)
        self.tasks = ['SATISFIES-PATTERN']
        parser = argparse.ArgumentParser()
        parser.add_argument("--kappa_url", help="kappa endpoint")
        args = parser.parse_args()
        if args.kappa_url:
            self.kappa_url = args.kappa_url
        else:
            logging.error('No Kappa URL given.')
            sys.exit()
        # Generate a basic model as placeholder (for testing)
        #model_text = 'MAPK1 binds MAP2K1.'
        #pa = PysbAssembler()
        #pa.add_statements(trips.process_text(model_text).statements)
        #self.model = pa.make_model()

        # Send subscribe messages
        for task in self.tasks:
            msg_txt =\
                '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.from_string(msg_txt))
        # Instantiate a singleton TRA agent
        kappa = kappa_client.KappaRuntime(self.kappa_url)
        self.tra = TRA(kappa)
        self.ready()
        super(TRA_Module, self).start()

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
        model_token = content_list.get_keyword_arg(':model')
        pattern_lst = content_list.get_keyword_arg(':pattern')
        conditions_lst = content_list.get_keyword_arg('conditions')

        try:
            model_str = str(model_token)
            model = decode_model(model_str)
        except Exception as e:
            logger.error(e)
            reply_content =\
                KQMLList.from_string('(FAILURE :reason INVALID_MODEL)')
            return reply_content

        try:
            pattern = get_temporal_pattern(pattern_lst)
            print pattern_lst
        except InvalidTimeUnitError as e:
            logger.error(e)
            reply_content =\
                KQMLList.from_string('(FAILURE :reason INVALID_TIME_LIMIT)')
            return reply_content
        except Exception as e:
            logger.error(e)
            reply_content =\
                KQMLList.from_string('(FAILURE :reason INVALID_PATTERN)')
            return reply_content
        if conditions_lst is None:
            conditions = None
        else:
            try:
                conditions = []
                for condition_lst in conditions_lst:
                    condition = get_molecular_condition(condition_lst)
                    conditions.append(condition)
            except Exception as e:
                logger.error(e)
                msg_str = '(FAILURE :reason INVALID_CONDITIONS)'
                reply_content = KQMLList.from_string(msg_str)
            return reply_content

        sat_rate, num_sim = \
            self.tra.check_property(model, pattern, conditions)

        reply_content = KQMLList()
        msg_str = '(:satisfies-rate %s :num-sim %d)' % (sat_rate, num_sim)
        reply_content.add('SUCCESS :content %s' % msg_str)
        return reply_content

def decode_model(model_str):
    try:
        s = model_str[1:-1].replace('\\"', '"')
        SelfExporter.do_export = True
        exec s
        SelfExporter.do_export = False
        return model
    except Exception as e:
        raise InvalidModelDescriptionError(e)

def get_string_arg(kqml_str):
    if kqml_str is None:
        return None
    s = kqml_str.to_string()
    if s[0] == '"':
        s = s[1:]
    if s[-1] == '"':
        s = s[:-1]
    s = s.replace('\\"', '"')
    return s

def get_molecular_entity(lst):
    try:
        description_ks = lst.get_keyword_arg(':description')
        description_str = get_string_arg(description_ks)
        tp = trips_processor.TripsProcessor(description_str)
        terms = tp.tree.findall('TERM')
        # TODO: handle multiple terms here
        term_id = terms[0].attrib['id']
        agent = tp._get_agent_by_id(term_id, None)
        return agent
    except Exception as e:
        raise InvalidMolecularEntityError(e)

def get_molecular_quantity(lst):
    try:
        quant_type = get_string_arg(lst.get_keyword_arg(':type'))
        value = get_string_arg(lst.get_keyword_arg(':value'))
        if quant_type == 'concentration':
            unit = get_string_arg(lst.get_keyword_arg(':unit'))
        else:
            unit = None
        return MolecularQuantity(quant_type, value, unit)
    except Exception as e:
        raise InvalidMolecularQuantityError(e)

def get_molecular_quantity_ref(lst):
    try:
        quant_type = get_string_arg(lst.get_keyword_arg(':type'))
        entity_lst = lst.get_keyword_arg(':entity')
        entity = get_molecular_entity(entity_lst)
        return MolecularQuantityReference(quant_type, entity)
    except Exception as e:
        raise InvalidMolecularQuantityRefError(e)

def get_time_interval(lst):
    try:
        lb = get_string_arg(lst.get_keyword_arg(':lower-bound'))
        ub = get_string_arg(lst.get_keyword_arg(':upper-bound'))
        unit = get_string_arg(lst.get_keyword_arg(':unit'))
        return TimeInterval(lb, ub, unit)
    except Exception as e:
        raise InvalidTimeIntervalError(e)

def get_temporal_pattern(lst):
    pattern_type = get_string_arg(lst.get_keyword_arg(':type'))
    entities_lst = lst.get_keyword_arg(':entities')
    entities = []
    for e in entities_lst:
        entity = get_molecular_entity(e)
        entities.append(entity)
    time_limit_lst = lst.get_keyword_arg('time-limit')
    if time_limit_lst is None:
        time_limit = None
    else:
        time_limit = get_time_interval(time_limit_lst)
    # TODO: handle more pattern-specific extra arguments
    return TemporalPattern(pattern_type, entities, time_limit)

def get_molecular_condition(lst):
    condition_type = get_string_arg(lst.get_keyword_arg(':type'))
    quantity_ref_lst = lst.get_keyword_arg(':quantity')
    quantity = get_molecular_quantity_ref(quantity_ref_lst)
    if condition_type == 'exact':
        value = get_molecular_quantity(lst.get_keyword_arg(':value'))
    elif condition_type == 'multiple':
        value = get_string_arg(lst.get_keyword_arg(':value'))
    elif condition_type in ['increase', 'decrease']:
        value = None
    else:
        raise InvalidMolecularConditionError('Unknown condition type: %s' %
                                             condition_type)
    return MolecularCondition(condition_type, quantity, value)

class InvalidModelDescriptionError(Exception):
    pass

if __name__ == "__main__":
    m = TRA_Module(['-name', 'TRA'] + sys.argv[1:])
