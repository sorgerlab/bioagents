import sys
import json
import logging
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('TRA')
import argparse
import tempfile

from indra import trips
from indra.assemblers import pysb_assembler, PysbAssembler
from indra.statements import Statement, stmts_from_json
from indra.trips import processor as trips_processor
from pysb import bng, Initial, Parameter, ComponentDuplicateNameError, \
                 SelfExporter

from bioagents.tra.tra import *
from bioagents.kappa import kappa_client
from kqml import KQMLModule, KQMLList, KQMLPerformative


class TRA_Module(KQMLModule):
    def __init__(self, argv, testing=False):
        parser = argparse.ArgumentParser()
        parser.add_argument("--kappa_url", help="kappa endpoint")
        args = parser.parse_args()
        self.kappa_url = None
        if args.kappa_url:
            self.kappa_url = args.kappa_url
        else:
            logger.error('No Kappa URL given.')
            self.kappa_url = None
            self.ode_mode = True
        # Instantiate a singleton TRA agent
        if self.kappa_url:
            try:
                kappa = kappa_client.KappaRuntime(self.kappa_url)
                self.ode_mode = False
            except Exception as e:
                logger.error('Could not instantiate TRA with Kappa service.')
                self.ode_mode = True

        if not self.ode_mode:
            self.tra = TRA(kappa)
        else:
            self.tra = TRA(None)

        if testing:
            return

        super(TRA_Module, self).__init__(argv)
        self.tasks = ['SATISFIES-PATTERN']

        # Send subscribe messages
        for task in self.tasks:
            msg_txt = \
                '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.from_string(msg_txt))
        self.ready()
        super(TRA_Module, self).start()

    def receive_request(self, msg, content):
        """Respond to an incoming request by handling different tasks."""
        if self.tra is None:
            reply_content = make_failure('KAPPA_FAILURE')
            reply_msg = KQMLPerformative('reply')
            reply_msg.set('content', reply_content)
            self.reply(msg, reply_msg)
            return

        task_str = content.head().upper()
        if task_str == 'SATISFIES-PATTERN':
            try:
                reply_content = self.respond_satisfies_pattern(content)
            except Exception:
                reply_content = make_failure('TRA_FAILURE')
        else:
            self.error_reply(msg, 'Unknown request task ' + task_str)
            return

        reply_msg = KQMLPerformative('reply')
        reply_msg.set('content', reply_content)
        self.reply(msg, reply_msg)

    def respond_satisfies_pattern(self, content):
        """Return response content to satisfies-pattern request."""
        model_indra_str = content.gets('model')
        pattern_lst = content.get('pattern')
        conditions_lst = content.get('conditions')

        try:
            model = assemble_model(model_indra_str)
        except Exception as e:
            logger.error(e)
            reply_content = make_failure('INVALID_MODEL')
            return reply_content

        try:
            pattern = get_temporal_pattern(pattern_lst)
        except InvalidTimeIntervalError as e:
            logger.error(e)
            reply_content = make_failure('INVALID_TIME_LIMIT')
            return reply_content
        except InvalidTemporalPatternError as e:
            logger.error(e)
            reply_content = make_failure('INVALID_PATTERN')
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
                reply_content = make_failure('INVALID_CONDITIONS')
                return reply_content

        try:
            sat_rate, num_sim, suggestion = \
                self.tra.check_property(model, pattern, conditions)
        except SimulatorError as e:
            logger.error(e)
            reply_content = make_failure('KAPPA_FAILURE')
            return reply_content
        except Exception as e:
            logger.error(e)
            reply_content = make_failure('INVALID_PATTERN')
            return reply_content

        reply = KQMLList('SUCCESS')
        content = KQMLList()
        content.set('satisfies-rate', '%.1f' % sat_rate)
        content.set('num-sim', '%d' % num_sim)
        if suggestion:
            sugg = KQMLList.from_string(suggestion)
            content.set('suggestion', sugg)
        reply.set('content', content)
        return reply

def decode_indra_stmts(stmts_json_str):
    stmts_json = json.loads(stmts_json_str)
    stmts = stmts_from_json(stmts_json)
    return stmts

def assemble_model(model_indra_str):
    stmts = decode_indra_stmts(model_indra_str)
    pa = PysbAssembler(policies='two_step')
    pa.add_statements(stmts)
    model = pa.make_model()
    pa.add_default_initial_conditions(100.0)
    for m in model.monomers:
        pysb_assembler.set_extended_initial_condition(model, m, 0)
    return model

def get_molecular_entity(lst):
    try:
        description_str = lst.gets('description')
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
        quant_type = lst.gets('type')
        value = lst.gets('value')
        if quant_type == 'concentration':
            unit = lst.gets('unit')
        else:
            unit = None
        return MolecularQuantity(quant_type, value, unit)
    except Exception as e:
        raise InvalidMolecularQuantityError(e)

def get_molecular_quantity_ref(lst):
    try:
        quant_type = lst.gets('type')
        entity_lst = lst.get('entity')
        entity = get_molecular_entity(entity_lst)
        return MolecularQuantityReference(quant_type, entity)
    except Exception as e:
        raise InvalidMolecularQuantityRefError(e)

def get_time_interval(lst):
    try:
        lb = lst.gets('lower-bound')
        ub = lst.gets('upper-bound')
        unit = lst.gets('unit')
        return TimeInterval(lb, ub, unit)
    except Exception as e:
        raise InvalidTimeIntervalError(e)

def get_temporal_pattern(lst):
    pattern_type = lst.gets('type')
    entities_lst = lst.get('entities')
    entities = []
    if entities_lst is None:
        entities_lst = []
    for e in entities_lst:
        entity = get_molecular_entity(e)
        entities.append(entity)
    time_limit_lst = lst.get('time-limit')
    if time_limit_lst is None:
        time_limit = None
    else:
        time_limit = get_time_interval(time_limit_lst)
    # TODO: handle more pattern-specific extra arguments
    value_lst = lst.get('value')
    if value_lst is not None:
        value = get_molecular_quantity(value_lst)
    else:
        value = None
    tp = TemporalPattern(pattern_type, entities, time_limit, value=value)
    return tp

def get_molecular_condition(lst):
    try:
        condition_type = lst.gets('type')
        quantity_ref_lst = lst.get('quantity')
        quantity = get_molecular_quantity_ref(quantity_ref_lst)
        if condition_type == 'exact':
            value = get_molecular_quantity(lst.get('value'))
        elif condition_type == 'multiple':
            value = lst.gets('value')
        else:
            value = None
        return MolecularCondition(condition_type, quantity, value)
    except Exception as e:
        raise InvalidMolecularConditionError(e)

def make_failure(reason):
    msg = KQMLList('FAILURE')
    msg.set('reason', reason)
    return msg

class InvalidModelDescriptionError(Exception):
    pass

if __name__ == "__main__":
    m = TRA_Module(['-name', 'TRA'] + sys.argv[1:])
