import os
import numpy
import itertools
from time import sleep
from bioagents.tra import kappa_client
from threading import Thread


TEST_MODEL_FILE = os.path.join(os.path.dirname(__file__), 'test_model.ka')


def _get_toy_model():
    fname = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         TEST_MODEL_FILE)
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
    kappa.add_file(TEST_MODEL_FILE)
    assert os.path.basename(TEST_MODEL_FILE) in kappa.get_files(),\
        "File not uploaded."


def test_code_upload():
    kappa = _get_kappa()
    original_files = kappa.get_files()
    kappa.add_code(kappa_model)
    assert len(original_files) < len(kappa.get_files()), "Code not added."


def test_parse():
    kappa = _get_kappa()
    res = kappa.compile([TEST_MODEL_FILE])
    print(res)


def test_run_sim():
    kappa = _get_kappa()
    kappa.compile([TEST_MODEL_FILE])
    print('Starting simulation')
    kappa.start_sim(plot_period=100)

    print('Started simulation')
    while True:
        sleep(1)
        print('Checking status')
        status = kappa.sim_status()
        print('Got status')
        is_running = status.get('simulation_progress_is_running')
        if not is_running:
            break
        else:
            print(status.get('simulation_progress_time'))
    kappa_plot = kappa.sim_plot()
    values = kappa_plot['series']
    nt = len(values)
    obs_list = [str(l[1:-1]) for l in kappa_plot['legend']]
    yobs = numpy.ndarray(nt, list(zip(obs_list, itertools.repeat(float))))

    tspan = []
    for t, value in enumerate(values):
        tspan.append(value[0])
        for i, obs in enumerate(obs_list):
            yobs[obs][t] = value[1]
    print(tspan, yobs)


def test_concurrency():
    exception_list = []

    def test_and_catch():
        try:
            test_file_upload()
        except Exception as e:
            exception_list.append(e)

    th_list = []
    for _ in range(2):
        th_list.append(Thread(target=test_and_catch))

    for th in th_list:
        th.start()

    for th in th_list:
        th.join()

    assert not len(exception_list),\
        "Receive exceptions from threads." + '\n'.join(
            [str(e) for e in exception_list]
            )
