import numpy
import logging
import itertools
from time import sleep
from pysb.export.kappa import KappaExporter

logger = logging.getLogger('TRA')

class TRA(object):
    def __init__(self, kappa):
        self.kappa = kappa
        kappa_ver = kappa.version()
        if kappa_ver is None or kappa_ver.get('version') is None:
            raise SimulatorError('Invalid Kappa client.')
        logger.debug('Using kappa version %s / build %s' %
                     (kappa_ver.get('version'), kappa_ver.get('build')))

    def check_property(self, model, pattern, conditions):
        if time_limit is None:
            #TODO: set this based on some model property
            max_time = 100.0
        elif time_limit.ub > 0:
            max_time = time_limit.ub
        tspan, yobs = self.simulate_model(model, conditions, max_time)

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
    for value in values:
        tspan.append(value['time'])
        for i, obs in enumerate(obs_list):
            yobs[obs] = value['values'][i]
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
