import os
import numpy
import itertools
from time import sleep
from bioagents.legacy.kappa import kappa_client


def _get_toy_model():
    fname = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'test_model.ka')
    with open(fname, 'rt') as fh:
        model = fh.read()
    return model


def _get_kappa():
    return kappa_client.KappaRuntime('test_project')


kappa_model = _get_toy_model()


def test_init_default():
    kappa = kappa_client.KappaRuntime()


def test_init_with_project():
    kappa = _get_kappa()


def test_version():
    kappa = _get_kappa()
    version = kappa.version()
    assert(version is not None)


def test_file_upload():
    kappa = _get_kappa()
    kappa.add_file('test_model.ka')
    assert 'test_model.ka' in kappa.get_files(), "File not uploaded."


def test_code_upload():
    kappa = _get_kappa()
    original_files = kappa.get_files()
    kappa.add_code(kappa_model)
    assert len(original_files) < len(kappa.get_files()), "Code not added."


def test_parse():
    kappa = _get_kappa()
    res = kappa.compile(['test_model.ka'])
    print(res)


def test_run_sim():
    kappa = _get_kappa()
    kappa.compile(['test_model.ka'])
    print('Starting simulation')
    sim_id = kappa.start(plot_period=100)
    assert(sim_id is not None)

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

