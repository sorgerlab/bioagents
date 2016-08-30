import numpy
import sympy.physics.units as units
import logging
import itertools
from time import sleep
import indra.statements as ist
import indra.assemblers.pysb_assembler as pa
from pysb.export.kappa import KappaExporter
from pysb import Observable
import model_checker as mc
from copy import deepcopy

logger = logging.getLogger('TRA')
import matplotlib.pyplot as plt

class TRA(object):
    def __init__(self, kappa):
        self.kappa = kappa
        kappa_ver = kappa.version()
        if kappa_ver is None or kappa_ver.get('version') is None:
            raise SimulatorError('Invalid Kappa client.')
        logger.debug('Using kappa version %s / build %s' %
                     (kappa_ver.get('version'), kappa_ver.get('build')))

    def check_property(self, model, pattern, conditions=None):
        if pattern.time_limit is None:
            #TODO: set this based on some model property
            max_time = 20000.0
        elif pattern.time_limit.ub > 0:
            max_time = time_limit.get_ub_seconds()
        # TODO: handle multiple entities
        obs = get_create_observable(model, pattern.entities[0])
        if pattern.pattern_type == 'transient':
            fstr = mc.transient_formula(obs.name)
        elif pattern.pattern_type == 'sustained':
            fstr = mc.sustained_formula(obs.name)
        elif pattern.pattern_type == 'no_change':
            fstr = mc.noact_formula(obs.name)
        elif pattern.pattern_type == 'always_value':
            if not pattern.value.quant_type == 'qualitative':
                msg = 'Cannot handle always value of "%s" type.' % \
                    pattern.value.quant_type
                raise InvalidTemporalPatternError(msg)
            if pattern.value.value == 'low':
                val = 0
            elif pattern.value.value == 'high':
                val = 1
            else:
                msg = 'Cannot handle always value of "%s".' % \
                    pattern.value.value
                raise InvalidTemporalPatternError(msg)
            fstr = mc.always_formula(obs.name, val)
        elif pattern.pattern_type == 'eventual_value':
            fstr = mc.eventual_formula(obs.name, pattern.value)
        elif pattern.pattern_type == 'sometime_value':
            fstr = mc.sometime_formula(obs.name, pattern.value)
        else:
            msg = 'Unknown pattern %s' % pattern.pattern_type
            raise InvalidTemporalPatternError(msg)
        # TODO: make this adaptive
        num_sim = 10
        num_times = 200
        if pattern.time_limit and pattern.time_limit.lb > 0:
            min_time = time_limit.get_lb_seconds()
            min_time_idx = int(num_times * (1.0*min_time / max_time))
        else:
            min_time_idx = 0
        truths = []
        plt.figure()
        plt.ion()
        for i in range(num_sim):
            logging.info('Simulation %d' % i)
            tspan, yobs = self.simulate_model(model, conditions, max_time, num_times)
            plt.plot(tspan, yobs)
            #print yobs
            self.discretize_obs(yobs, obs.name)
            yobs_from_min = yobs[min_time_idx:]
            MC = mc.ModelChecker(fstr, yobs_from_min)
            tf = MC.truth
            truths.append(tf)
        plt.savefig('%s.png' % fstr)
        sat_rate = numpy.count_nonzero(truths) / (1.0*num_sim)
        return sat_rate, num_sim

    def discretize_obs(self, yobs, obs_name):
        # TODO: This needs to be done in a model/observable-dependent way
        for i, v in enumerate(yobs[obs_name]):
            yobs[obs_name][i] = 1 if v > 50 else 0

    def simulate_model(self, model, conditions, max_time, num_times):
        # Set up simulation conditions
        if conditions:
            model_sim = deepcopy(model)
            for condition in conditions:
                apply_condition(model, condition)
        else:
            model_sim = model
        # Export kappa model
        kappa_model = pysb_to_kappa(model_sim)
        # Start simulation
        kappa_params = {'code': kappa_model,
                        'max_time': max_time,
                        'nb_plot': num_times}
        sim_id = self.kappa.start(kappa_params)
        while True:
            sleep(0.2)
            status = self.kappa.status(sim_id)
            is_running = status.get('is_running')
            if not is_running:
                break
            else:
                logging.info('Sim event percentage: %d' %
                              status.get('event_percentage'))
        tspan, yobs = get_sim_result(status.get('plot'))
        return tspan, yobs

def apply_condition(model, condition):
    agent = condition.quantity.entity
    monomer = model.monomers[agent.name]
    site_pattern = pa.get_site_pattern(agent)
    # TODO: handle modified patterns
    if site_pattern:
        logger.warning('Cannot handle initial conditions on' +
                       ' modified monomers.')
    if condition.condition_type == 'exact':
        if condition.value.quant_type == 'number':
            pa.set_base_initial_condition(model, monomer,
                                          condition.value.value)
        else:
            logger.warning('Cannot handle non-number initial conditions')
    elif condition.condition_type == 'multiple':
        # TODO: refer to annotations for the IC name
        ic_name = monomer.name + '_0'
        model.parameters[ic_name].value *= condition.value
    elif condition.condition_type == 'decrease':
        ic_name = monomer.name + '_0'
        model.parameters[ic_name].value *= 0.9
    elif condition.condition_type == 'increase':
        ic_name = monomer.name + '_0'
        model.parameters[ic_name].value *= 1.1

def get_create_observable(model, agent):
    site_pattern = pa.get_site_pattern(agent)
    obs_name = pa.get_agent_rule_str(agent) + '_obs'
    monomer = model.monomers[agent.name]
    obs = Observable(obs_name, monomer(site_pattern))
    model.add_component(obs)
    return obs

def pysb_to_kappa(model):
    ke = KappaExporter(model)
    kappa_model = ke.export()
    return kappa_model

def get_sim_result(kappa_plot):
    values = kappa_plot['observables']
    values.sort(key = lambda x: x['time'])
    nt = len(values)
    obs_list = [str(l[1:-1]) for l in kappa_plot['legend']]
    yobs = numpy.ndarray(nt, list(zip(obs_list, itertools.repeat(float))))

    tspan = []
    for t, value in enumerate(values):
        tspan.append(value['time'])
        for i, obs in enumerate(obs_list):
            yobs[obs][t] = value['values'][i]
    return (tspan, yobs)

class TemporalPattern(object):
    def __init__(self, pattern_type, entities, time_limit, *args, **kwargs):
        self.pattern_type = pattern_type
        self.entities = entities
        self.time_limit = time_limit
        # TODO: handle extra arguments by pattern type
        if self.pattern_type in \
            ('always_value', 'eventual_value', 'sometime_value'):
            value = kwargs.get('value')
            if value is None:
                msg = 'Missing molecular quantity'
                raise InvalidTemporalPatternError(msg)
            self.value = value


class MolecularCondition(object):
    def __init__(self, condition_type, quantity, value=None):
        if isinstance(quantity, MolecularQuantityReference):
            self.quantity = quantity
        else:
            msg = 'Invalid molecular quantity reference'
            raise InvalidMolecularConditionError(msg)
        if condition_type == 'exact':
            if isinstance(value, MolecularQuantity):
                self.value = value
            else:
                msg = 'Invalid molecular condition value'
                raise InvalidMolecularConditionError(msg)
        elif condition_type == 'multiple':
            try:
                value_num = float(value)
                if value_num < 0:
                    raise ValueError('Negative molecular quantity not allowed')
            except ValueError as e:
                raise InvalidMolecularConditionError(e)
            self.value = value_num
        elif condition_type in ['increase', 'decrease']:
            self.value = None
        else:
            msg = 'Unknown condition type: %s' % condition_type
            raise InvalidMolecularConditionError(msg)
        self.condition_type = condition_type

class MolecularQuantity(object):
    def __init__(self, quant_type, value, unit=None):
        if quant_type == 'concentration':
            try:
                value_num = float(value)
            except ValueError:
                msg = 'Invalid concentration value %s' % value
                raise InvalidMolecularQuantityError(msg)
            if unit == 'mM':
                sym_value = value_num * units.milli * units.mol / units.liter
            elif unit == 'uM':
                sym_value = value_num * units.micro * units.mol / units.liter
            elif unit == 'nM':
                sym_value = value_num * units.nano * units.mol / units.liter
            elif unit == 'pM':
                sym_value = value_num * units.pico * units.mol / units.liter
            else:
                msg = 'Invalid unit %s' % unit
                raise InvalidMolecularQuantityError(msg)
            self.value = sym_value
        elif quant_type == 'number':
            try:
                value_num = int(value)
                if value_num < 0:
                    raise ValueError
            except ValueError:
                msg = 'Invalid molecule number value %s' % value
                raise InvalidMolecularQuantityError(msg)
            self.value = value_num
        elif quant_type == 'qualitative':
            if value in ['low', 'high']:
                self.value = value
            else:
                msg = 'Invalid qualitative quantity value %s' % value
                raise InvalidMolecularQuantityError(msg)
        else:
            raise InvalidMolecularQuantityError('Invalid quantity type %s' %
                                                quant_type)
        self.quant_type = quant_type

class MolecularQuantityReference(object):
    def __init__(self, quant_type, entity):
        if quant_type in ['total', 'initial']:
            self.quant_type = quant_type
        else:
            msg = 'Unknown quantity type %s' % quant_type
            raise InvalidMolecularQuantityRefError(msg)
        if not isinstance(entity, ist.Agent):
            msg = 'Invalid molecular Agent'
            raise InvalidMolecularQuantityRefError(msg)
        else:
            self.entity = entity

class TimeInterval(object):
    def __init__(self, lb, ub, unit):
        if unit == 'day':
            sym_unit = units.day
        elif unit == 'hour':
            sym_unit = units.hour
        elif unit == 'minute':
            sym_unit = units.minute
        elif unit == 'second':
            sym_unit = units.second
        else:
            raise InvalidTimeIntervalError('Invalid unit %s' % unit)
        if lb is not None:
            try:
                lb_num = float(lb)
            except ValueError:
                raise InvalidTimeIntervalError('Invalid bound %s' % lb)
            self.lb = lb_num * sym_unit
        else:
            self.lb = None
        if ub is not None:
            try:
                ub_num = float(ub)
            except ValueError:
                raise InvalidTimeIntervalError('Invalid bound %s' % ub)
            self.ub = ub_num * sym_unit
        else:
            self.ub = None

    def get_lb_seconds(self):
        if self.lb is not None:
            return self.lb / units.second
        return None

    def get_ub_seconds(self):
        if self.ub is not None:
            return self.ub / units.second
        return None

class InvalidMolecularQuantityError(Exception):
    pass

class InvalidMolecularQuantityRefError(Exception):
    pass

class InvalidMolecularEntityError(Exception):
    pass

class InvalidMolecularConditionError(Exception):
    pass

class InvalidTemporalPatternError(Exception):
    pass

class InvalidTimeIntervalError(Exception):
    pass

class SimulatorError(Exception):
    pass
