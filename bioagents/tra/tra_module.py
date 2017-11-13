import sys
import json
import logging
from kqml import KQMLList, KQMLPerformative
from indra.assemblers import pysb_assembler, PysbAssembler
from indra.statements import stmts_from_json, Activation, Inhibition, \
    ActiveForm
from indra.sources.trips import processor as trips_processor
from bioagents.tra import tra
from bioagents.tra import kappa_client
from bioagents import Bioagent, BioagentException

# This version of logging is coming from tra...
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('TRA')


class TRA_Module(Bioagent):
    name = "TRA"
    tasks = ['SATISFIES-PATTERN', 'MODEL-COMPARE-CONDITIONS']

    def __init__(self, **kwargs):
        use_kappa = True
        if (('argv' in kwargs.keys() and '--no_kappa' in kwargs['argv'])
           or ('no_kappa' in kwargs.keys() and kwargs['no_kappa'])):
            use_kappa = False
            if 'no_kappa' in kwargs.keys():
                kwargs.pop('no_kappa')

        # Instantiate a singleton TRA agent
        self.ode_mode = True
        if use_kappa:
            try:
                kappa = kappa_client.KappaRuntime('TRA_simulations')
                self.ode_mode = False
            except Exception as e:
                logger.error('Could not instantiate TRA with Kappa service.')
                logger.exception(e)
        else:
            logger.warning('You have chosen to not use Kappa.')

        if not self.ode_mode:
            self.tra = tra.TRA(kappa)
        else:
            self.tra = tra.TRA()

        return super(TRA_Module, self).__init__(**kwargs)

    def respond_satisfies_pattern(self, content):
        """Return response content to satisfies-pattern request."""
        model_indra_str = content.gets('model')
        pattern_lst = content.get('pattern')
        conditions_lst = content.get('conditions')

        try:
            stmts = decode_indra_stmts(model_indra_str)
            model = assemble_model(stmts)
        except Exception as e:
            logger.exception(e)
            reply_content = self.make_failure('INVALID_MODEL')
            return reply_content

        try:
            pattern = get_temporal_pattern(pattern_lst)
        except tra.InvalidTimeIntervalError as e:
            logger.exception(e)
            reply_content = self.make_failure('INVALID_TIME_LIMIT')
            return reply_content
        except tra.InvalidTemporalPatternError as e:
            logger.exception(e)
            reply_content = self.make_failure('INVALID_PATTERN')
            return reply_content
        except tra.InvalidMolecularEntityError as e:
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
        except tra.MissingMonomerError as e:
            logger.exception(e)
            reply_content = self.make_failure('MODEL_MISSING_MONOMER')
            return reply_content
        except tra.MissingMonomerSiteError as e:
            logger.exception(e)
            reply_content = self.make_failure('MODEL_MISSING_MONOMER_SITE')
            return reply_content
        except tra.SimulatorError as e:
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

    def respond_model_compare_conditions(self, content):
        condition_agent_ekb = content.gets('agent')
        target_agent_ekb = content.gets('affected')
        model_indra_str = content.gets('model')
        try:
            stmts = decode_indra_stmts(model_indra_str)
            model = assemble_model(stmts)
        except Exception as e:
            logger.exception(e)
            reply_content = self.make_failure('INVALID_MODEL')
            return reply_content
        try:
            condition_agent = get_single_molecular_entity(condition_agent_ekb)
            target_agent = get_single_molecular_entity(target_agent_ekb)
        except Exception as e:
            logger.exception(e)
            reply_content = self.make_failure('INVALID_PATTERN')
            return reply_content
        try:
            result, fig_path = \
                self.tra.compare_conditions(model, condition_agent,
                                            target_agent)
        except tra.MissingMonomerError as e:
            logger.exception(e)
            reply_content = self.make_failure('MODEL_MISSING_MONOMER')
            return reply_content
        except tra.MissingMonomerSiteError as e:
            logger.exception(e)
            reply_content = self.make_failure('MODEL_MISSING_MONOMER_SITE')
            return reply_content
        except tra.SimulatorError as e:
            logger.exception(e)
            reply_content = self.make_failure('KAPPA_FAILURE')
            return reply_content

        self.send_display_figure(fig_path)

        reply = KQMLList('SUCCESS')
        reply.set('result', result)
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


def assemble_model(stmts):
    pa = PysbAssembler(policies='two_step')
    pa.add_statements(stmts)
    model = pa.make_model()
    pa.add_default_initial_conditions(100.0)

    try:
        targeted_agents = get_targeted_agents(stmts)
        no_upstream_active_agents = get_no_upstream_active_agents(stmts)
    except:
        targeted_agents = []
        no_upstream_active_agents = []
    try:
        chemical_agents = get_chemical_agents(stmts)
    except:
        chemical_agents = []

    for m in model.monomers:
        try:
            if m.name in targeted_agents or m.name in no_upstream_active_agents:
                pysb_assembler.set_base_initial_condition(model,
                    model.monomers[m.name], 50.0)
                pysb_assembler.set_extended_initial_condition(model, m, 50.0)
            elif m.name in chemical_agents:
                pysb_assembler.set_base_initial_condition(model,
                    model.monomers[m.name], 10000.0)
            else:
                pysb_assembler.set_extended_initial_condition(model, m, 0)
        except:
            pysb_assembler.set_extended_initial_condition(model, m, 0)
    # Tweak parameters
    for param in model.parameters:
        if 'kf' in param.name and 'bind' in param.name:
            param.value = param.value * 100
    return model


def get_targeted_agents(stmts):
    """Return agents that are inhibited while not being activated by anything.
    """
    has_act = set()
    has_inh = set()
    for stmt in stmts:
        if isinstance(stmt, Activation):
            has_act.add(stmt.obj.name)
        elif isinstance(stmt, Inhibition):
            has_inh.add(stmt.obj.name)
    inh_not_act = list(has_inh - has_act)
    return inh_not_act


def get_no_upstream_active_agents(stmts):
    """Return agents that are active but there's nothing upstream.
    """
    has_act = set()
    has_upstream = set()
    for stmt in stmts:
        if isinstance(stmt, Activation):
            has_upstream.add(stmt.obj.name)
        elif isinstance(stmt, ActiveForm):
            has_upstream.add(stmt.agent.name)
        for agent in stmt.agent_list():
            if agent is not None:
                if agent.activity is not None and agent.activity.is_active:
                    has_act.add(agent.name)
    act_no_ups = list(has_act - has_upstream)
    return act_no_ups


def get_chemical_agents(stmts):
    chemicals = set()
    for stmt in stmts:
        for agent in stmt.agent_list():
            if agent is not None and ('CHEBI' in agent.db_refs or
                                      'PC' in agent.db_refs):
                chemicals.add(pysb_assembler._n(agent.name))
    return list(chemicals)


def get_molecular_entity(lst):
    description_str = lst.gets('description')
    return get_single_molecular_entity(description_str)


def get_single_molecular_entity(description_str):
    try:
        tp = trips_processor.TripsProcessor(description_str)
        terms = tp.tree.findall('TERM')
        def find_complex(terms):
            cplx = None
            for term in terms:
                term_type = term.find('type')
                if term_type is not None and \
                    term_type.text == 'ONT::MACROMOLECULAR-COMPLEX':
                    cplx = term.attrib.get('id')
                    break
            return cplx
        cplx_id = find_complex(terms)
        if not cplx_id:
            term_id = terms[0].attrib['id']
            logger.info('Using ID of term: %s' % term_id)
        else:
            logger.info('Using ID of complex: %s' % cplx_id)
            term_id = cplx_id
        agent = tp._get_agent_by_id(term_id, None)
        return agent
    except Exception as e:
        raise tra.InvalidMolecularEntityError(e)


def get_molecular_quantity(lst):
    try:
        quant_type = lst.gets('type')
        value = lst.gets('value')
        if quant_type == 'concentration':
            unit = lst.gets('unit')
        else:
            unit = None
        return tra.MolecularQuantity(quant_type, value, unit)
    except Exception as e:
        raise tra.InvalidMolecularQuantityError(e)


def get_molecular_quantity_ref(lst):
    try:
        quant_type = lst.gets('type')
        entity_lst = lst.get('entity')
        entity = get_molecular_entity(entity_lst)
        return tra.MolecularQuantityReference(quant_type, entity)
    except Exception as e:
        raise tra.InvalidMolecularQuantityRefError(e)


def get_time_interval(lst):
    try:
        lb = lst.gets('lower-bound')
        ub = lst.gets('upper-bound')
        unit = lst.gets('unit')
        return tra.TimeInterval(lb, ub, unit)
    except Exception as e:
        raise tra.InvalidTimeIntervalError(e)


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
    tp = tra.TemporalPattern(pattern_type, entities, time_limit, value=value)
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
        return tra.MolecularCondition(condition_type, quantity, value)
    except Exception as e:
        raise tra.InvalidMolecularConditionError(e)


class InvalidModelDescriptionError(BioagentException):
    pass


if __name__ == "__main__":
    m = TRA_Module(argv=sys.argv[1:])
