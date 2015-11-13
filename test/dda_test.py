from bioagents import dda

def test_mutation_statistics():
    d = dda.DDA()
    mutation_dict = d.get_mutation_statistics('pancreatic', 'missense')
    assert(mutation_dict['KRAS'] > 0)
