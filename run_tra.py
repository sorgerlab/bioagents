import numpy
import re
from pysb.integrate import Solver
from model_checker import *

from test_model import model


def run_query(model, query):
    m = re.match('Is the amount of (.+) ([^ ]+) in time?', query)
    target_str = m.groups()[0]
    pattern_str = m.groups()[1]

    ts = numpy.linspace(0, 100, 10)
    solver = Solver(model, ts)
    solver.run()

    if target_str == 'A-B complex':
        target = 'AB'

    for i, a in enumerate(solver.yobs[target]):
        solver.yobs[target][i] = 1 if a > 50 else 0

    if pattern_str == 'sustained':
        fstr = sustained_formula(target)
    elif pattern_str == 'unchanged':
        fstr = noact_formula(target)

    print 'LTL formula: %s' % fstr
    mc = ModelChecker(fstr, solver.yobs)
    print 'Result:', mc.truth

query = 'Is the amount of A-B complex sustained in time?'
run_query(model, query)

