import numpy
import itertools
from time import sleep
from bioagents.kappa import kappa_client

kappa = kappa_client.KappaRuntime('http://maasha.org:8080')

with open('test_model.ka', 'rt') as fh:
    kappa_model = fh.read()

kappa_params = {'code': kappa_model,
                'plot_period': 10000,
                'nb_plot': 100}
sim_id = kappa.start(kappa_params)

while True:
    sleep(0.2)
    status = kappa.status(sim_id)
    is_running = status.get('is_running')
    if not is_running:
        break
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
