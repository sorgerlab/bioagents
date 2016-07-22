import numpy
import sympy.physics.units as units
import logging
import itertools
from time import sleep
import indra.assemblers.pysb_assembler as pa
from pysb.export.kappa import KappaExporter
from pysb import Observable
import model_checker as mc

logger = logging.getLogger('TRA')

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
        else:
            msg = 'Unknown pattern %s' % pattern.pattern_type
            raise InvalidTemporalPatternError(msg)
        # TODO: make this adaptive
        num_sim = 10
        num_times = 100
        if pattern.time_limit.lb > 0:
            min_time = time_limit.get_lb_seconds()
            min_time_idx = int(num_times * (1.0*min_time / max_time))
        else:
            min_time_idx = 0
        truths = []
        for i in range(num_sim):
            tspan, yobs = self.simulate_model(model, conditions, max_time, num_times)
            #print yobs
            self.discretize_obs(yobs, obs.name)
            yobs_from_min = yobs[min_time_idx:]
            MC = mc.ModelChecker(fstr, yobs_from_min)
            tf = MC.truth
            truths.append(tf)
        sat_rate = numpy.count_nonzero(truths) / (1.0*num_sim)
        return sat_rate, num_sim

    def discretize_obs(self, yobs, obs_name):
        # TODO: This needs to be done in a model/observable-dependent way
        for i, v in enumerate(yobs[obs_name]):
            yobs[obs_name][i] = 1 if v > 50 else 0

    def simulate_model(self, model, conditions, max_time, num_times):
        # Export kappa model
        kappa_model = pysb_to_kappa(model)
        # Set up simulation conditions

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
                logging.debug('Sim event percentage: %d' %
                              status.get('event_percentage'))
        tspan, yobs = get_sim_result(status.get('plot'))
        return tspan, yobs

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

class MolecularCondition(object):
    def __init__(self, condition_type, quantity, value):
        self.condition_type = condition_type
        self.quantity = quantity
        self.value = value

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
        self.quant_type = quant_type
        self.entity = entity

class TimeInterval(object):
    def __init__(self, lb, ub, unit):
        if unit == 'hour':
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

class InvalidMolecularEntityError(Exception):
    pass

class InvalidTemporalPatternError(Exception):
    pass

class InvalidTimeIntervalError(Exception):
    pass

class SimulatorError(Exception):
    pass
