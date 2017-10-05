import sys
import json
import logging
from kqml import KQMLList, KQMLPerformative
from indra.assemblers import pysb_assembler, PysbAssembler
from indra.statements import stmts_from_json
from indra.sources.trips import processor as trips_processor
from bioagents.tra.tra import TRA, SimulatorError, tra_molecule, tra_time
from bioagents.tra import kappa_client
from bioagents import Bioagent, BioagentException

# This version of logging is coming from tra...
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('TRA')


class TRA_Module(Bioagent):
    name = "TRA"
    tasks = ['SATISFIES-PATTERN']

    def __init__(self, **kwargs):
        use_kappa = True
        if 'argv' in kwargs.keys() and '--no_kappa' in kwargs['argv']:
            use_kappa = False

        # Instantiate a singleton TRA agent
        self.ode_mode = True
        if use_kappa:
            try:
                kappa = kappa_client.KappaRuntime('TRA_modelling')
                self.ode_mode = False
            except Exception as e:
                logger.error('Could not instantiate TRA with Kappa service.')
                logger.exception(e)
        else:
            logger.warning('You have chose to not use Kappa.')

        if not self.ode_mode:
            self.tra = TRA(kappa)
        else:
            self.tra = TRA()

        return super(TRA_Module, self).__init__(**kwargs)

    def respond_satisfies_pattern(self, content):
        """Return response content to satisfies-pattern request."""
        model_indra_str = content.gets('model')
        pattern_lst = content.get('pattern')
        conditions_lst = content.get('conditions')

        try:
            model = assemble_model(model_indra_str)
        except Exception as e:
            logger.exception(e)
            reply_content = self.make_failure('INVALID_MODEL')
            return reply_content

        try:
            pattern = get_temporal_pattern(pattern_lst)
        except tra_time.InvalidIntervalError as e:
            logger.exception(e)
            reply_content = self.make_failure('INVALID_TIME_LIMIT')
            return reply_content
        except tra_time.InvalidPatternError as e:
            logger.exception(e)
            reply_content = self.make_failure('INVALID_PATTERN')
            return reply_content
        except tra_molecule.InvalidEntityError as e:
            logger.exception(e)
            reply_content = self.make_failure('INVALID_ENTITY_DESCRIPTION')
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
                logger.exception(e)
                reply_content = self.make_failure('INVALID_CONDITIONS')
                return reply_content

        try:
            sat_rate, num_sim, suggestion, fig_path = \
                self.tra.check_property(model, pattern, conditions)
        except SimulatorError as e:
            logger.exception(e)
            reply_content = self.make_failure('KAPPA_FAILURE')
            return reply_content
        except Exception as e:
            logger.exception(e)
            reply_content = self.make_failure('INVALID_PATTERN')
            return reply_content

        self.send_display_figure(fig_path)

        reply = KQMLList('SUCCESS')
        content = KQMLList()
        content.set('satisfies-rate', '%.1f' % sat_rate)
        content.set('num-sim', '%d' % num_sim)
        if suggestion:
            sugg = KQMLList.from_string(suggestion)
            content.set('suggestion', sugg)
        reply.set('content', content)
        return reply

    def send_display_figure(self, path):
        msg = KQMLPerformative('tell')
        content = KQMLList('display-image')
        content.set('type', 'simulation')
        content.sets('path', path)
        msg.set('content', content)
        self.send(msg)


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
        raise tra_molecule.InvalidEntityError(e)


def get_molecular_quantity(lst):
    try:
        quant_type = lst.gets('type')
        value = lst.gets('value')
        if quant_type == 'concentration':
            unit = lst.gets('unit')
        else:
            unit = None
        return tra_molecule.Quantity(quant_type, value, unit)
    except Exception as e:
        raise tra_molecule.InvalidQuantityError(e)


def get_molecular_quantity_ref(lst):
    try:
        quant_type = lst.gets('type')
        entity_lst = lst.get('entity')
        entity = get_molecular_entity(entity_lst)
        return tra_molecule.QuantityReference(quant_type, entity)
    except Exception as e:
        raise tra_molecule.InvalidQuantityRefError(e)


def get_time_interval(lst):
    try:
        lb = lst.gets('lower-bound')
        ub = lst.gets('upper-bound')
        unit = lst.gets('unit')
        return tra_time.Interval(lb, ub, unit)
    except Exception as e:
        raise tra_time.InvalidIntervalError(e)


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
    tp = tra_time.Pattern(pattern_type, entities, time_limit, value=value)
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
        return tra_molecule.Condition(condition_type, quantity, value)
    except Exception as e:
        raise tra_molecule.InvalidConditionError(e)


class InvalidModelDescriptionError(BioagentException):
    pass


if __name__ == "__main__":
    m = TRA_Module(argv=sys.argv[1:])
