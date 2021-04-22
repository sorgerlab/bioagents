"""Web API client for a Kappa simulator."""

import kappy
from logging import getLogger, DEBUG

logger = getLogger('kappa_client')


KAPPA_URL = 'https://api.executableknowledge.org/kappa'


class KappaRuntime(object):
    def __init__(self, project_name=None, debug=False, use_rest=False):
        """Create a Kappa client."""
        if debug:
            logger.setLevel(DEBUG)
        if use_rest:
            self.kappa_instance = kappy.KappaRest(KAPPA_URL,
                                                  project_id=project_name)
            self.kappa_instance.get_info()
        else:
            self.kappa_instance = kappy.KappaStd()
        return

    def add_code(self, code_str, name=None):
        """Add a code string to the project."""
        self.kappa_instance.add_model_string(code_str, file_id=name)
        return

    def compile(self, fname_list=None, code_list=None):
        """Parse given Kappa files and any other files that have been added.

        Parameters
        ----------
        fname_list : List or None
            A list of local file names (ending in `.ka`) to be added to the
            project before compiling. None by default, indicating no new files.
        code_list : List or None
            A list of code strings to be added to the project before compiling.
            None by default, indicating no new strings.
        """
        for fname in [] if fname_list is None else fname_list:
            self.kappa_instance.add_model_file(fname, file_id=fname)
        for code_str in [] if code_list is None else code_list:
            self.kappa_instance.add_model_string(code_str)
        content = self.kappa_instance.project_parse()
        return content

    def start_sim(self, **parameters):
        """Start a simulation with given parameters.

        Note that parameters are subject to changes in the kappa remote api.

        Parameters
        ----------
        plot_period : int or float
            The time period between output (plot) points returned by the
            simulation. Default: 10
        pause_condition : string or None
            A Kappa Boolean expression defining a pause condition for the
            simulation. Default: None
        seed: int
            A random seed for the stochastic simulation. Default: None
        store_trace : bool
            Presumably you can choose whether to store the trace. Hopefully
            interpretation is straightforward. Default: True
        """
        complete_params = {
            'plot_period': 10,
            'pause_condition': '[false]',
            'seed': None,
            'store_trace': True
            }
        complete_params.update(parameters)
        sim_params = kappy.SimulationParameter(**complete_params)
        self.kappa_instance.simulation_start(sim_params)

    def pause_sim(self):
        """Pause a given simulation."""
        self.kappa_instance.simulation_pause()

    def continue_sim(self):
        """Continue the pause simulation."""
        self.kappa_instance.simulation_continue()

    def sim_status(self):
        """Return status of running simulation."""
        return self.kappa_instance.simulation_info()

    def sim_plot(self):
        """Get the data from the simulation."""
        return self.kappa_instance.simulation_plot()
