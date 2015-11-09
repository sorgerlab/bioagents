# MEA stands for model execution agent.
# Its task is to simulate models and interpret
# the simulation output.

import warnings
import numpy
import matplotlib.pyplot as plt
import pysb
from pysb.integrate import Solver

class MEA:
    def __init__(self):
        pass

    def get_monomer(self, model, agent):
        '''
        Return the monomer from a model corresponding to a given
        agent.
        '''
        try:
            monomer = model.monomers[agent.name]
        except KeyError:
            warnings.warn('Monomer of interest %s could not be '
                          'found in model.' % agent.name)
            monomer = None
        return monomer
    
    def get_create_observable(self, model, obs_name, obs_pattern):
        '''
        Try to create an observable with the given name and pattern or 
        if it already exists in the model then return it.
        '''
        try:
            obs = pysb.Observable(obs_name, obs_pattern)
            model.add_component(obs)
        except pysb.ComponentDuplicateNameError:
            return model.observables[obs_name]
        return obs

    def get_obs_name(self, model, monomer):
        # TODO: how do we know that we are looking for an active species?
        return monomer.name + '_act'

    def simulate_model(self, model, agent_target):
        '''
        Simulate a model and return the observed dynamics of 
        a given target agent.
        '''
        monomer = self.get_monomer(model, agent_target)
        obs_name = self.get_obs_name(model, monomer)
        obs_pattern = monomer(act='active')
        self.get_create_observable(model, obs_name, obs_pattern)
        # TODO: where does the maximal time point come from?
        ts = numpy.linspace(0, 100, 100)
        try:
            solver = Solver(model, ts)
        except pysb.bng.GenerateNetworkError:
            warnings.warn('Could not generate network')
            return None
        solver.run()
        yobs_target = solver.yobs[obs_name]
        plt.ion()
        plt.plot(ts, yobs_target, label=obs_name)
        plt.show()
        plt.legend()
        return yobs_target

if __name__ == '__main__':
    pass
