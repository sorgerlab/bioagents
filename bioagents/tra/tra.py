import numpy
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
            max_time = time_limit.ub
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
        truths = []
        for i in range(num_sim):
            tspan, yobs = self.simulate_model(model, conditions, max_time)
            logger.debug(yobs)
            self.discretize_obs(yobs, obs.name)
            MC = mc.ModelChecker(fstr, yobs)
            tf = MC.truth
            truths.append(tf)
        sat_rate = len(numpy.where(truths)) / (1.0*num_sim)
        return sat_rate, num_sim

    def discretize_obs(self, yobs, obs_name):
        # TODO: This needs to be done in a model/observable-dependent way
        for i, v in enumerate(yobs[obs_name]):
            yobs[obs_name][i] = 1 if v > 50 else 0

    def simulate_model(self, model, conditions, max_time):
        # Export kappa model
        kappa_model = pysb_to_kappa(model)
        # Set up simulation conditions
        # Start simulation
        nb_plot = 100
        kappa_params = {'code': kappa_model,
                        'max_time': max_time,
                        'nb_plot': nb_plot}
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

class MolecularCondition(object):
    def __init__(self, condition_type, quantity, value):
        self.condition_type = condition_type
        self.quantity = quantity
        self.value = value

class MolecularQuantity(object):
    def __init__(self, quant_type, value, unit=None):
        if quant_type == 'concentration':
            unit = lst.get_keyword_arg(':unit')
            try:
                value_num = float(falue)
            except ValueError:
                msg = 'Invalid quantity type %s' % quant_type
                raise InvalidMolecularQuantityError(msg)
            pass
        elif quant_type == 'number':
            pass
        elif quant_type == 'qualitative':
            if value == 'high':
                pass
            elif value == 'low':
                pass
            else:
                msg = 'Invalid qualitative quantity value %s' % value
                raise InvalidMolecularQuantityError(msg)
            pass
        else:
            raise InvalidMolecularQuantityError('Invalid quantity type %s' %
                                                quant_type)
        self.quant_type = quant_type
        self.value = value
        self.unit = unit

class MolecularQuantityReference(object):
    def __init__(self, quant_type, entity):
        self.quant_type = quant_type
        self.entity = entity

class TimeInterval(object):
    def __init__(self, lb, ub, unit):
        self.lb = lb
        self.ub = ub
        self.unit = unit

class InvalidMolecularQuantityError(Exception):
    pass

class InvalidMolecularEntityError(Exception):
    pass

class InvalidTemporalPatternError(Exception):
    pass

class SimulatorError(Exception):
    pass
