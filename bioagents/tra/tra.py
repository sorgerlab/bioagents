from bioagents.tra import kappa_client
__all__ = ['TRA', 'get_ltl_from_pattern', 'apply_condition',
           'get_create_observable', 'pysb_to_kappa', 'get_sim_result',
           'get_all_patterns', 'TemporalPattern', 'TimeInterval',
           'InvalidTemporalPatternError', 'InvalidTimeIntervalError',
           'MolecularCondition', 'MolecularQuantity',
           'MolecularQuantityReference', 'InvalidMolecularConditionError',
           'InvalidMolecularQuantityError',
           'InvalidMolecularQuantityRefError', 'SimulatorError']
import os
import numpy
import logging
from time import sleep
from typing import List
from copy import deepcopy
from datetime import datetime
import sympy.physics.units as units
import indra.statements as ist
import indra.assemblers.pysb.assembler as pa
from indra.assemblers.english import assembler as english_assembler
from pysb import Observable
from pysb.integrate import Solver
from pysb.export.kappa import KappaExporter
from pysb.core import ComponentDuplicateNameError
import bioagents.tra.model_checker as mc
import matplotlib
from bioagents import BioagentException, get_img_path

matplotlib.use('Agg')
import matplotlib.pyplot as plt


logger = logging.getLogger('TRA')


class TRA(object):
    def __init__(self, use_kappa=True, use_kappa_rest=False):
        kappa_mode_label = 'rest' if use_kappa_rest else 'standard'
        if not use_kappa:
            self.ode_mode = True
            logger.info('Using ODE mode in TRA.')
        else:
            self.ode_mode = False
            try:
                self.kappa = kappa_client.KappaRuntime('TRA_simulations',
                                                       use_rest=use_kappa_rest)
                logger.info('Using kappa %s.' % kappa_mode_label)
            except Exception as e:
                logger.error('Could not use kappa %s.' % kappa_mode_label)
                logger.exception(e)
                self.ode_mode = True
        return

    def check_property(self, model, pattern, conditions=None,
                       max_time=None, num_times=None, num_sim=2):
        # TODO: handle multiple entities (observables) in pattern
        # TODO: set max_time based on some model property if not given
        # NOTE: pattern.time_limit.ub takes precedence over max_time
        # Make an observable for the simulations
        logger.info('Trying to make an observable for: %s',
                    pattern.entities[0])
        obs = get_create_observable(model, pattern.entities[0])

        # Make pattern
        fstr = get_ltl_from_pattern(pattern, obs)
        given_pattern = (fstr is not None)

        # Set the time limit for the simulations
        if pattern.time_limit is not None and pattern.time_limit.ub > 0:
            # Convert sympy.Float to regular float
            max_time = float(pattern.time_limit.get_ub_seconds())
        elif not max_time:
            max_time = 20000
        if not num_times:
            num_times = 100
        # The period at which the output is sampled
        plot_period = int(1.0*max_time / num_times)
        if pattern.time_limit and pattern.time_limit.lb > 0:
            min_time = pattern.time_limit.get_lb_seconds()
            min_time_idx = int(num_times * (1.0*min_time / max_time))
        else:
            min_time_idx = 0

        # Run simulations
        if given_pattern and num_sim == 0:
            from .model_checker import HypothesisTester
            ht = HypothesisTester(prob=0.8, alpha=0.1, beta=0.1, delta=0.05)
            yobs_list = []
            results = []
            thresholds = []
            truths = []
            while True:
                result = self.run_simulations(model, conditions, 1,
                                               min_time_idx, max_time, plot_period)[0]
                results.append(result)
                yobs = deepcopy(result[1])
                threshold = self.discretize_obs(model, yobs, obs.name)
                MC = mc.ModelChecker(fstr, yobs)
                logger.info('Main property %s' % MC.truth)
                truths.append(MC.truth)
                thresholds.append(threshold)
                yobs_list.append(yobs)
                ht_result = ht.test(truths)
                if ht_result is not None:
                    break
            # TODO: this is not that pretty, maybe a separate input argument
            # would be better
            num_sim = len(results)
            results_copy = deepcopy(results)
            sat_rate = numpy.count_nonzero(truths) / (1.0 * num_sim)
            make_suggestion = (sat_rate < 0.3)
            if make_suggestion:
                logger.info('MAKING SUGGESTION with sat rate %.2f.' % sat_rate)
        else:
            results = self.run_simulations(model, conditions, num_sim,
                                           min_time_idx, max_time,
                                           plot_period)

            results_copy = deepcopy(results)
            yobs_list = [yobs for _, yobs in results]

            # Discretize observations
            # WARNING: yobs is changed by discretize_obs in place
            thresholds = [self.discretize_obs(model, yobs, obs.name)
                          for yobs in yobs_list]
            # We check for the given pattern
            if given_pattern:
                truths = []
                for yobs in yobs_list:
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

        fig_path = self.plot_results(results_copy, pattern.entities[0],
                                     obs.name, thresholds[0])

        # If no suggestion is to be made, we return
        if not make_suggestion:
            return sat_rate, num_sim, None, None, fig_path

        # Run model checker on all patterns
        all_patterns = get_all_patterns(obs.name)
        for fs, kpat, pat_obj in all_patterns:
            logger.info('Testing pattern: %s' % kpat)
            truths = []
            for yobs in yobs_list:
                MC = mc.ModelChecker(fs, yobs)
                logger.info('Property %s' % MC.truth)
                truths.append(MC.truth)
            sat_rate_new = numpy.count_nonzero(truths) / (1.0*num_sim)
            if sat_rate_new > 0.5:
                if not given_pattern:
                    return sat_rate_new, num_sim, kpat, pat_obj, fig_path
                else:
                    return sat_rate, num_sim, kpat, pat_obj, fig_path

    def compare_conditions(self, model, condition_agent, target_agent, up_dn,
                           max_time=None, num_times=101):
        if not max_time:
            max_time = 20000
        if not num_times:
            num_times = 101
        obs = get_create_observable(model, target_agent)
        cond_quant = MolecularQuantityReference('total', condition_agent)
        all_results = []
        plot_period = max_time / (num_times - 1)
        ts = numpy.linspace(0, max_time, num_times)
        mults = [0.0, 100.0]
        for mult in mults:
            condition = MolecularCondition('multiple', cond_quant, mult)
            results = self.run_simulations(model, [condition], 1, 0,
                                           max_time, plot_period)
            obs_values = results[0][1][obs.name]
            all_results.append(obs_values)
        # Plotting
        fig_path = self.plot_compare_conditions(ts, all_results, target_agent,
                                                obs.name)
        diff = numpy.sum(all_results[-1][:len(ts)] -
                         all_results[0][:len(ts)]) / len(ts)
        logger.info('TRA condition difference: %.2f' % diff)
        # If there is a decrease in the observable, we return True
        if abs(diff) < 0.01:
            res = 'no_change'
        elif up_dn == 'dn':
            res = 'yes_decrease' if (diff < 0) else 'no_increase'
        else:
            res = 'no_decrease' if (diff < 0) else 'yes_increase'

        return res, fig_path

    def plot_compare_conditions(self, ts, results, agent, obs_name):
        max_val_lim = max((numpy.max(results[0]) + 0.25*numpy.max(results[0])),
                          (numpy.max(results[1]) + 0.25*numpy.max(results[1])),
                          101.0)
        plt.figure()
        plt.ion()
        plt.plot(ts, results[0][:len(ts)], label='Without condition')
        plt.plot(ts, results[-1][:len(ts)], label='With condition')
        plt.ylim(-5, max_val_lim)
        plt.xlabel('Time (s)')
        plt.ylabel('Amount (molecules)')
        agent_str = english_assembler._assemble_agent_str(agent).agent_str
        plt.title('Simulation results for %s' % agent_str)
        plt.legend()
        fig_path = get_img_path(obs_name + '.png')
        plt.savefig(fig_path)
        return fig_path

    def plot_results(self, results, agent, obs_name, thresh=50):
        plt.figure()
        plt.ion()
        max_val_lim = max(max((numpy.max(results[0][1][obs_name]) + 0.25*numpy.max(results[0][1][obs_name])), 101.0),
                          thresh)
        max_time = max([result[0][-1] for result in results])
        lr = matplotlib.patches.Rectangle((0, 0), max_time, thresh, color='red',
                                          alpha=0.1)
        hr = matplotlib.patches.Rectangle((0, thresh), max_time,
                                          max_val_lim-thresh,
                                          color='green', alpha=0.1)
        ax = plt.gca()
        ax.add_patch(lr)
        ax.add_patch(hr)
        if thresh + 0.05*max_val_lim < max_val_lim:
            plt.text(10, thresh + 0.05*max_val_lim, 'High', fontsize=10)
        plt.text(10, thresh - 0.05*max_val_lim, 'Low')
        for tspan, yobs in results:
            plt.plot(tspan, yobs[obs_name])
        plt.ylim(-5, max_val_lim)
        plt.xlim(-max_time/100, max_time+max_time/100)
        plt.xlabel('Time (s)')
        plt.ylabel('Amount (molecules)')
        agent_str = english_assembler._assemble_agent_str(agent).agent_str
        plt.title('Simulation results for %s' % agent_str)
        fig_path = get_img_path(obs_name + '.png')
        plt.savefig(fig_path)
        return fig_path

    def run_simulations(self, model, conditions, num_sim, min_time_idx,
                        max_time, plot_period):
        logger.info('Running %d simulations with time limit of %d and plot '
                    'period of %d.' % (num_sim, max_time, plot_period))
        self.sol = None
        results = []
        for i in range(num_sim):
            # Apply molecular condition to model
            try:
                model_sim = self.condition_model(model, conditions)
            except MissingMonomerError as e:
                raise e
            except Exception as e:
                logger.exception(e)
                msg = 'Applying molecular condition failed.'
                raise InvalidMolecularConditionError(msg)
            # Run a simulation
            logger.info('Starting simulation %d' % (i+1))
            if not self.ode_mode:
                try:
                    tspan, yobs = self.simulate_kappa(model_sim, max_time,
                                                      plot_period)
                except Exception as e:
                    logger.exception(e)
                    raise SimulatorError('Kappa simulation failed.')
            else:
                tspan, yobs = self.simulate_odes(model_sim, max_time,
                                                 plot_period)
            # Get and plot observable
            start_idx = min(min_time_idx, len(yobs))
            yobs_from_min = yobs[start_idx:]
            tspan = tspan[start_idx:]
            results.append((tspan, yobs_from_min))
        return results

    def discretize_obs(self, model, yobs, obs_name):
        # TODO: This needs to be done in a model/observable-dependent way
        default_total_val = 100
        start_val = yobs[obs_name][0]
        max_val = numpy.max(yobs[obs_name])
        min_val = numpy.min(yobs[obs_name])
        # If starts low, discretize wrt total value
        if start_val < 1e-5:
            thresh = 0.3 * default_total_val
        # If starts high, discretize wrt range with a certain minimum
        else:
            thresh = start_val + max(0.5*(max_val - min_val),
                                     default_total_val * 0.10)
        for i, v in enumerate(yobs[obs_name]):
            yobs[obs_name][i] = 1 if v > thresh else 0
        return thresh

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
        self.kappa.compile(code_list=[kappa_model])
        self.kappa.start_sim(plot_period=plot_period,
                         pause_condition="[T] > %d" % max_time)
        while True:
            sleep(0.2)
            status_json = self.kappa.sim_status()['simulation_info_progress']
            is_running = status_json.get('simulation_progress_is_running')
            if not is_running:
                break
            else:
                if status_json.get('time_percentage') is not None:
                    logger.info(
                        'Sim time percentage: %d' %
                        status_json.get('simulation_progress_time_percentage')
                        )
        tspan, yobs = get_sim_result(self.kappa.sim_plot())
        self.kappa.reset_project()
        return tspan, yobs

    def simulate_odes(self, model_sim, max_time, plot_period):
        ts = numpy.linspace(0, max_time, int(1.0*max_time/plot_period) + 1)
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
    elif pattern.pattern_type in ('no_change', 'always_value'):
        if not hasattr(pattern, 'value') or pattern.value is None:
            fstr = mc.noact_formula(obs.name)
        elif not pattern.value.quant_type == 'qualitative':
            msg = 'Cannot handle always value of "%s" type.' % \
                pattern.value.quant_type
            raise InvalidTemporalPatternError(msg)
        else:
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
    try:
        monomer = model.monomers[pa._n(agent.name)]
    except KeyError:
        raise MissingMonomerError('%s is not in the model ' % agent.name,
                                  agent)
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
    try:
        monomer = model.monomers[pa._n(agent.name)]
    except KeyError:
        raise MissingMonomerError('%s is not in the model ' % agent.name,
                                  agent)
    try:
        monomer_state = monomer(site_pattern)
    except Exception as e:
        msg = 'Site pattern %s invalid for monomer %s' % \
            (site_pattern, monomer.name)
        raise MissingMonomerSiteError(msg)
    obs = Observable(obs_name, monomer(site_pattern))
    try:
        model.add_component(obs)
    except ComponentDuplicateNameError as e:
        pass
    return obs


def pysb_to_kappa(model):
    ke = KappaExporter(model)
    kappa_model = ke.export()
    return kappa_model


def get_sim_result(kappa_plot):
    values = kappa_plot['series']
    i_t = kappa_plot['legend'].index('[T]')
    values.sort(key=lambda x: x[i_t])
    nt = len(values)
    obs_dict = {
        j: key for j, key in enumerate(kappa_plot['legend'])
        if key != '[T]'
        }
    yobs = numpy.ndarray(
        nt, list(zip(obs_dict.values(), [float]*len(obs_dict))))
    tspan = []
    for i, value in enumerate(values):
        tspan.append(value[i_t])
        for j, obs in obs_dict.items():
            yobs[obs][i] = value[j]
    return (tspan, yobs)


def get_all_patterns(obs_name):
    patterns = []

    # Always high/low
    for val_num, val_str in zip((0, 1), ('low', 'high')):
        fstr = mc.always_formula(obs_name, val_num)
        kpattern = (
            '(:type "no_change" '
            ':value (:type "qualitative" :value "%s"))' % val_str
            )
        pattern = TemporalPattern('no_change', [], None,
                                  value=MolecularQuantity('qualitative',
                                                          '%s' % val_str))
        patterns.append((fstr, kpattern, pattern))

    # Eventually high/low
    for val_num, val_str in zip((0, 1), ('low', 'high')):
        fstr = mc.eventual_formula(obs_name, val_num)
        kpattern = (
            '(:type "eventual_value" '
            ':value (:type "qualitative" :value "%s"))' % val_str
            )
        pattern = TemporalPattern('eventual_value', [], None,
                                  value=MolecularQuantity('qualitative',
                                                          '%s' % val_str))
        patterns.append((fstr, kpattern, pattern))

    # Transient
    fstr = mc.transient_formula(obs_name)
    kpattern = '(:type "transient")'
    pattern = TemporalPattern('transient', [], None)
    patterns.append((fstr, kpattern, pattern))

    # Sustined
    fstr = mc.sustained_formula(obs_name)
    kpattern = '(:type "sustained")'
    pattern = TemporalPattern('sustained', [], None)
    patterns.append((fstr, kpattern, pattern))

    # Sometime high/low
    for val_num, val_str in zip((0, 1), ('low', 'high')):
        fstr = mc.sometime_formula(obs_name, val_num)
        kpattern = (
            '(:type "sometime_value" '
            ':value (:type "qualitative" :value "%s"))' % val_str
            )
        pattern = TemporalPattern('sometime_value', [], None,
                                  value=MolecularQuantity('qualitative',
                                                          '%s' % val_str))
        patterns.append((fstr, kpattern, pattern))

    # No change any value
    fstr = mc.noact_formula(obs_name)
    kpattern = '(:type "no_change")'
    pattern = TemporalPattern('no_change', [], None)
    patterns.append((fstr, kpattern, pattern))

    return patterns


# #############################################################
# Classes for representing time intervals and temporal patterns
# #############################################################


class TemporalPattern(object):
    """A temporal pattern"""
    def __init__(self, pattern_type: str, entities: List[ist.Agent], time_limit, **kwargs):
        self.pattern_type = pattern_type
        self.entities = entities
        self.time_limit = time_limit
        # TODO: handle extra arguments by pattern type
        if self.pattern_type in \
           ('always_value', 'no_change', 'eventual_value', 'sometime_value'):
            value = kwargs.get('value')
            if value is None:
                # Value is optional for no_change
                if self.pattern_type != 'no_change':
                    msg = 'Missing molecular quantity'
                    raise InvalidTemporalPatternError(msg)
            self.value = value


class InvalidTemporalPatternError(BioagentException):
    pass


class TimeInterval(object):
    def __init__(self, lb, ub, unit: str):
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
                raise InvalidTimeIntervalError('Bad bound %s' % lb)
            self.lb = lb_num * sym_unit
        else:
            self.lb = None
        if ub is not None:
            try:
                ub_num = float(ub)
            except ValueError:
                raise InvalidTimeIntervalError('Bad bound %s' % ub)
            self.ub = ub_num * sym_unit
        else:
            self.ub = None

    def _convert_to_sec(self, val):
        if val is not None:
            try:
                # sympy >= 1.1
                return units.convert_to(val, units.seconds).args[0]
            except Exception:
                # sympy < 1.1
                return val / units.seconds
        return None

    def get_lb_seconds(self):
        return self._convert_to_sec(self.lb)

    def get_ub_seconds(self):
        return self._convert_to_sec(self.ub)


class InvalidTimeIntervalError(BioagentException):
    pass


# ############################################################
# Classes for representing molecular quantities and conditions
# ############################################################

class MolecularQuantityReference(object):
    def __init__(self, quant_type: str, entity: ist.Agent):
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


class MolecularQuantity(object):
    def __init__(self, quant_type: str, value: str, unit: str = None):
        if quant_type == 'concentration':
            try:
                val = float(value)
            except ValueError:
                msg = 'Invalid concentration value %s' % value
                raise InvalidMolecularQuantityError(msg)
            if unit == 'mM':
                sym_value = val * units.milli * units.mol / units.liter
            elif unit == 'uM':
                sym_value = val * units.micro * units.mol / units.liter
            elif unit == 'nM':
                sym_value = val * units.nano * units.mol / units.liter
            elif unit == 'pM':
                sym_value = val * units.pico * units.mol / units.liter
            else:
                msg = 'Invalid unit %s' % unit
                raise InvalidMolecularQuantityError(msg)
            self.value = sym_value
        elif quant_type == 'number':
            try:
                val = int(value)
                if val < 0:
                    raise ValueError
            except ValueError:
                msg = 'Invalid molecule number value %s' % value
                raise InvalidMolecularQuantityError(msg)
            self.value = val
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


class MolecularCondition(object):
    def __init__(self, condition_type: str,
                 quantity: MolecularQuantityReference,
                 value: MolecularQuantity = None):
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


class InvalidMolecularQuantityError(BioagentException):
    pass


class InvalidMolecularQuantityRefError(BioagentException):
    pass


class InvalidMolecularEntityError(BioagentException):
    pass


class InvalidMolecularConditionError(BioagentException):
    pass


class MissingMonomerError(BioagentException):
    def __init__(self, message, monomer):
        super().__init__(message)
        self.monomer = monomer


class MissingMonomerSiteError(BioagentException):
    pass


class SimulatorError(BioagentException):
    pass
