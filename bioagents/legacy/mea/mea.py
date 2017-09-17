# MEA stands for model execution agent.
# Its task is to simulate models and interpret
# the simulation output.

import numpy
import matplotlib.pyplot as plt
import logging
import pysb
from pysb.integrate import Solver

logger = logging.getLogger('MEA')

class InvalidTargetException(Exception):
    def __init__(self, *args, **kwargs):
            Exception.__init__(self, *args, **kwargs)


class InvalidConditionException(Exception):
    def __init__(self, *args, **kwargs):
            Exception.__init__(self, *args, **kwargs)


class MEA:
    def __init__(self):
        pass

    def get_monomer(self, model, entity):
        '''
        Return the monomer from a model corresponding to a given
        agent.
        '''
        try:
            monomer = model.monomers[entity]
        except KeyError:
            logger.warning('Monomer of interest %s could not be '
                           'found in model.' % entity)
            monomer = None
        return monomer

    def get_create_observable(self, model, obs_name, obs_pattern):
        '''
        Try to create an observable with the given name and pattern or
        if it already exists in the model then return it.
        '''
        try:
            obs = pysb.Observable(str(obs_name), obs_pattern)
            model.add_component(obs)
        except pysb.ComponentDuplicateNameError:
            obs = model.observables[obs_name]
        return obs

    def get_obs_name(self, model, monomer):
        # TODO: how do we know that we are looking for an active species?
        return monomer.name + '_act'

    def compare_auc(self, ts, y_ref, y_new):
        '''
        Return the ratio of the area under two simulation trajectories,
        y_new and y_ref.
        '''
        dt = numpy.diff(ts)
        a_ref = numpy.dot(dt, 0.5*(y_ref[1:] + y_ref[:-1]))
        a_new = numpy.dot(dt, 0.5*(y_new[1:] + y_new[:-1]))
        return a_new / a_ref

    def compare_conditions(self, model, target_entity, target_pattern,
                           condition_entity, condition_pattern):
        '''
        Compare model simulation target with or without adding a given agent.
        '''
        monomer = self.get_monomer(model, target_entity)
        obs_name = self.get_obs_name(model, monomer)
        if target_pattern == 'active':
            obs_pattern = monomer(act='active')
        elif target_pattern == 'inactive':
            obs_pattern = monomer(act='inactive')
        else:
            logger.error('Unhandled target pattern: %s' % target_pattern)
            raise InvalidTargetException
        self.get_create_observable(model, obs_name, obs_pattern)
        if condition_pattern in ['add', 'remove']:
            # Get the monomer whose addition is of interest
            monomer = self.get_monomer(model, condition_entity)
            # Get the name of the initial conditions for the monomer
            # TODO: how do we know that the name is always
            # constructed as below?
            init_cond_name = condition_entity + '_0'
            init_orig = model.parameters[init_cond_name].value
            # Simulate without the monomer
            model.parameters[init_cond_name].value = 0
            yobs_target_noadd =\
                self.simulate_model(model, target_entity)
            # Simulate with the monomer
            # TODO: where does this value come from?
            model.parameters[init_cond_name].value = 100
            yobs_target_add =\
                self.simulate_model(model, target_entity)
            # Restore the original initial condition value
            model.parameters[init_cond_name].value = init_orig
            # TODO: this should be obtained from simulate_model
            ts = numpy.linspace(0, 100, 100)
            auc_ratio = self.compare_auc(ts, yobs_target_noadd,
                                         yobs_target_add)
            if condition_pattern == 'add':
                return (auc_ratio > 1)
            else:
                return (auc_ratio < 1)

    def check_pattern(self, model, target_entity, target_pattern):
        monomer = self.get_monomer(model, target_entity)
        obs_name = self.get_obs_name(model, monomer)
        if target_pattern == 'active':
            obs_pattern = monomer(act='active')
        elif target_pattern == 'inactive':
            obs_pattern = monomer(act='active')
        else:
            logger.error('Unhandled target pattern: %s' % target_pattern)
            raise InvalidTargetException
        self.get_create_observable(model, obs_name, obs_pattern)
        yobs_target = self.simulate_model(model, target_entity)
        if numpy.any(yobs_target > 0):
            return True
        else:
            return False

    def simulate_model(self, model, target_entity):
        '''
        Simulate a model and return the observed dynamics of
        a given target agent.
        '''
        # TODO: where does the maximal time point come from?
        monomer = self.get_monomer(model, target_entity)
        obs_name = self.get_obs_name(model, monomer)
        ts = numpy.linspace(0, 100, 100)
        solver = Solver(model, ts)
        solver.run()
        yobs_target = solver.yobs[obs_name]
        plt.ion()
        plt.plot(ts, yobs_target, label=obs_name)
        plt.show()
        plt.legend()
        return yobs_target

if __name__ == '__main__':
    pass
