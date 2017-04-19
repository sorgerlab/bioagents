from kqml import KQMLList
from bioagents.dtda import DTDA
from bioagents.dtda import DTDA_Module

def test_mutation_statistics():
    d = DTDA()
    mutation_dict = \
        d.get_mutation_statistics('pancreatic carcinoma', 'missense')
    assert(mutation_dict['KRAS'] > 0)
