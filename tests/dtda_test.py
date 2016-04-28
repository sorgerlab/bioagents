from bioagents import dtda

def test_mutation_statistics():
    d = dtda.DTDA()
    mutation_dict = d.get_mutation_statistics('pancreatic', 'missense')
    assert(mutation_dict['KRAS'] > 0)
