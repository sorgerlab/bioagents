from bioagents import nextprot_client

def test_get_family_members():
    protein_names = nextprot_client.get_family_members('03114')
    assert(len(protein_names)==3)
    assert('BRAF' in protein_names)
