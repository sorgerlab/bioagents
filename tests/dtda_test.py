from bioagents.dtda import DTDA

def test_mutation_statistics():
    d = DTDA()
    mutation_dict = d.get_mutation_statistics('pancreatic', 'missense')
    assert(mutation_dict['KRAS'] > 0)
