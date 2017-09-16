import os
import numpy
import itertools
from time import sleep
from bioagents.kappa import kappa_client

kappa = kappa_client.KappaRuntime()

def test_version():
    version = kappa.version()
    assert(version == 4)

if __name__ == '__main__':
    fname = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'test_model.ka')
    with open(fname, 'rt') as fh:
        kappa_model = fh.read()

    kappa_params = {'code': kappa_model,
                    'plot_period': 100,
                    'max_time': 10000}
    print('Starting simulation')
    sim_id = kappa.start(kappa_params)
    print('Started simulation')

    while True:
        sleep(1)
        print('Checking status')
        status = kappa.status(sim_id)
        print('Got status')
        is_running = status.get('is_running')
        if not is_running:
            break
        else:
            print(status.get('time_percentage'))
    kappa_plot = status.get('plot')

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
    print(tspan, yobs)
