import numpy
import logging
import itertools
from time import sleep
from copy import deepcopy
from collections import defaultdict
import sympy.physics.units as units
import indra.statements as ist
import indra.assemblers.pysb_assembler as pa
from pysb import Observable
from pysb.integrate import Solver
from pysb.export.kappa import KappaExporter
import model_checker as mc

logger = logging.getLogger('TRA')
import matplotlib
import matplotlib.pyplot as plt

class TRA(object):
    def __init__(self, kappa):
        if kappa is None:
            self.ode_mode = True
        else:
            self.ode_mode = False
        if not self.ode_mode:
            self.kappa = kappa
            kappa_ver = kappa.version()
            if kappa_ver is None or kappa_ver.get('version_id') is None:
                raise SimulatorError('Invalid Kappa client.')
            logger.info('Using kappa version %s / build %s' %
                         (kappa_ver.get('version_id'),
                          kappa_ver.get('version_build')))
        else:
            logger.info('Using ODE mode in TRA.')

    def check_property(self, model, pattern, conditions=None):
        # TODO: handle multiple entities (observables) in pattern
        # TODO: set max_time based on some model property if not given
        # TODO: make number of simulations and number of time points adaptive

        # Make an observable for the simulations
        obs = get_create_observable(model, pattern.entities[0])

        # Make pattern
        fstr = get_ltl_from_pattern(pattern, obs)
        given_pattern = (fstr is not None)

        # Set the time limit for the simulations
        if pattern.time_limit is None:
            max_time = 20000.0
        elif pattern.time_limit.ub > 0:
            max_time = time_limit.get_ub_seconds()
        # The numer of time points to get output at
        num_times = 100
        # The periof at which the output is sampled
        plot_period = int(1.0*max_time / num_times)
        if pattern.time_limit and pattern.time_limit.lb > 0:
            min_time = time_limit.get_lb_seconds()
            min_time_idx = int(num_times * (1.0*min_time / max_time))
        else:
            min_time_idx = 0

        # The number of independent simulations to perform
        num_sim = 10
        # Run simulations
        tspan, results = self.run_simulations(model, conditions, num_sim,
                                              min_time_idx, max_time,
                                              plot_period)

        self.plot_results(tspan, results, obs.name)

        # Discretize observations
        [self.discretize_obs(yobs, obs.name) for yobs in results]
        # We check for the given pattern
        if given_pattern:
            truths = []
            for yobs in results:
                # Run model checker on the given pattern
                MC = mc.ModelChecker(fstr, yobs)
                logger.info('Main property %s' % MC.truth)
                truths.append(MC.truth)
            sat_rate = numpy.count_nonzero(truths) / (1.0*num_sim)
            make_suggestion = (sat_rate < 0.3)
            if make_suggestion:
                logger.info('MAKING SUGGESTION with sat rate %.2f.' % sat_rate)
        else:
            make_suggestion = True

        # If no suggestion is to be made, we return
        if not make_suggestion:
            return sat_rate, num_sim, None

        # Run model checker on all patterns
        all_patterns = get_all_patterns(obs.name)
        for fs, pat in all_patterns:
            logger.info('Testing pattern: %s' % pat)
            truths = []
            for yobs in results:
                MC = mc.ModelChecker(fs, yobs)
                logger.info('Property %s' % MC.truth)
                truths.append(MC.truth)
            sat_rate_new = numpy.count_nonzero(truths) / (1.0*num_sim)
            if sat_rate_new > 0.5:
                if not given_pattern:
                    return sat_rate_new, num_sim, pat
                else:
                    return sat_rate, num_sim, pat

    def plot_results(self, tspan, results, obs_name):
        plt.figure()
        plt.ion()
        lr = matplotlib.patches.Rectangle((0,0), tspan[-1], 50, color='red',
                                           alpha=0.1)
        hr = matplotlib.patches.Rectangle((0,50), tspan[-1], 50, color='green',
                                           alpha=0.1)
        ax = plt.gca()
        ax.add_patch(lr)
        ax.add_patch(hr)
        for yobs in results:
            plt.plot(tspan, yobs[obs_name])
        plt.ylim(0, max(numpy.max(yobs[obs_name]), 100.0))
        plt.xlabel('Time (s)')
        plt.ylabel('Amount (molecules)')
        plt.title('Simulation results')
        plt.savefig('%s.png' % obs_name)

    def run_simulations(self, model, conditions, num_sim, min_time_idx,
                        max_time, plot_period):
        self.sol = None
        results = []
        for i in range(num_sim):
            # Apply molecular condition to model
            try:
                model_sim = self.condition_model(model, conditions)
            except Exception as e:
                logger.error(e)
                msg = 'Applying molecular condition failed.'
                raise InvalidMolecularConditionError(msg)
            # Run a simulation
            logger.info('Starting simulation %d' % (i+1))
            if not self.ode_mode:
                try:
                    tspan, yobs = self.simulate_kappa(model_sim, max_time,
                                                      plot_period)
                except Exception as e:
                    logger.error(e)
                    raise SimulatorError('Kappa simulation failed.')
            else:
                tspan, yobs = self.simulate_odes(model_sim, max_time,
                                                 plot_period)
            # Get and plot observable
            yobs_from_min = yobs[min_time_idx:]
            results.append(yobs)
        return tspan, results

    def discretize_obs(self, yobs, obs_name):
        # TODO: This needs to be done in a model/observable-dependent way
        for i, v in enumerate(yobs[obs_name]):
            yobs[obs_name][i] = 1 if v > 50 else 0

    def condition_model(self, model, conditions):
        # Set up simulation conditions
        if conditions:
            model_sim = deepcopy(model)
            for condition in conditions:
                apply_condition(model_sim, condition)
        else:
            model_sim = model
        return model_sim

    def simulate_kappa(self, model_sim, max_time, plot_period):
        # Export kappa model
        kappa_model = pysb_to_kappa(model_sim)
        # Start simulation
        kappa_params = {'code': kappa_model,
                        'plot_period': plot_period,
                        'max_time': max_time}
        sim_id = self.kappa.start(kappa_params)
        while True:
            sleep(0.2)
            status = self.kappa.status(sim_id)
            is_running = status.get('is_running')
            if not is_running:
                break
            else:
                if status.get('time_percentage') is not None:
                    logger.info('Sim time percentage: %d' %
                                  status.get('time_percentage'))
        tspan, yobs = get_sim_result(status.get('plot'))
        return tspan, yobs

    def simulate_odes(self, model_sim, max_time, plot_period):
        ts = numpy.linspace(0, max_time, int(1.0*max_time/plot_period))
        if self.sol is None:
            self.sol = Solver(model_sim, ts)
        self.sol.run()
        return ts, self.sol.yobs

def get_ltl_from_pattern(pattern, obs):
    if not pattern.pattern_type:
        return None
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
        if not pattern.value.quant_type == 'qualitative':
            msg = 'Cannot handle eventual value of "%s" type.' % \
                pattern.value.quant_type
            raise InvalidTemporalPatternError(msg)
        if pattern.value.value == 'low':
            val = 0
        elif pattern.value.value == 'high':
            val = 1
        else:
            msg = 'Cannot handle eventual value of "%s".' % \
                pattern.value.value
            raise InvalidTemporalPatternError(msg)
        fstr = mc.eventual_formula(obs.name, val)
    elif pattern.pattern_type == 'sometime_value':
        if not pattern.value.quant_type == 'qualitative':
            msg = 'Cannot handle sometime value of "%s" type.' % \
                pattern.value.quant_type
            raise InvalidTemporalPatternError(msg)
        if pattern.value.value == 'low':
            val = 0
        elif pattern.value.value == 'high':
            val = 1
        else:
            msg = 'Cannot handle sometime value of "%s".' % \
                pattern.value.value
            raise InvalidTemporalPatternError(msg)
        fstr = mc.sometime_formula(obs.name, val)
    else:
        msg = 'Unknown pattern %s' % pattern.pattern_type
        raise InvalidTemporalPatternError(msg)
    return fstr

def apply_condition(model, condition):
    agent = condition.quantity.entity
    monomer = model.monomers[pa._n(agent.name)]
    site_pattern = pa.get_site_pattern(agent)
    # TODO: handle modified patterns
    if site_pattern:
        logger.warning('Cannot handle initial conditions on' +
                       ' modified monomers.')
    if condition.condition_type == 'exact':
        ic_name = monomer.name + '_0'
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
    logger.info('New initial condition: %s' % model.parameters[ic_name])

def get_create_observable(model, agent):
    site_pattern = pa.get_site_pattern(agent)
    obs_name = pa.get_agent_rule_str(agent) + '_obs'
    monomer = model.monomers[pa._n(agent.name)]
    obs = Observable(obs_name.encode('utf-8'), monomer(site_pattern))
    model.add_component(obs)
    return obs

def pysb_to_kappa(model):
    ke = KappaExporter(model)
    kappa_model = ke.export()
    return kappa_model

def get_sim_result(kappa_plot):
    values = kappa_plot['time_series']
    values.sort(key = lambda x: x['observation_time'])
    nt = len(values)
    obs_list = [str(l[1:-1]) for l in kappa_plot['legend']]
    yobs = numpy.ndarray(nt, list(zip(obs_list, itertools.repeat(float))))

    tspan = []
    for t, value in enumerate(values):
        tspan.append(value['observation_time'])
        for i, obs in enumerate(obs_list):
            yobs[obs][t] = value['observation_values'][i]
    return (tspan, yobs)

def get_all_patterns(obs_name):
    patterns = []
    for val_num, val_str in zip((0, 1), ('low', 'high')):
        fstr = mc.always_formula(obs_name, val_num)
        pattern = \
            '(:type "always_value" :value (:type "qualitative" :value "%s"))' % val_str
        patterns.append((fstr, pattern))
    for val_num, val_str in zip((0, 1), ('low', 'high')):
        fstr = mc.eventual_formula(obs_name, val_num)
        pattern = \
            '(:type "eventual_value" :value (:type "qualitative" :value "%s"))' % val_str
        patterns.append((fstr, pattern))
    fstr = mc.transient_formula(obs_name)
    pattern = '(:type "transient")'
    patterns.append((fstr, pattern))
    fstr = mc.sustained_formula(obs_name)
    pattern = '(:type "sustained")'
    patterns.append((fstr, pattern))
    for val_num, val_str in zip((0, 1), ('low', 'high')):
        fstr = mc.sometime_formula(obs_name, val_num)
        pattern = \
            '(:type "sometime_value" :value (:type "qualitative" :value "%s"))' % val_str
        patterns.append((fstr, pattern))
    fstr = mc.noact_formula(obs_name)
    pattern = '(:type "no_change")'
    patterns.append((fstr, pattern))
    return patterns

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
