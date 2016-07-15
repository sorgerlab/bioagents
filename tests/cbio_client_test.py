from bioagents.databases import cbio_client

def test_get_cancer_studies():
    study_ids = cbio_client.get_cancer_studies('paad')
    assert(len(study_ids) > 0)
    assert('paad_tcga' in study_ids)

def test_get_cancer_types():
    type_ids = cbio_client.get_cancer_types('lung')
    assert(len(type_ids) > 0)

def test_get_genetic_profiles():
    genetic_profiles = cbio_client.get_genetic_profiles('paad_icgc', 'mutation')
    assert(len(genetic_profiles) > 0)

def test_get_num_sequenced():
    num_case = cbio_client.get_num_sequenced('paad_tcga')
    assert(num_case > 0)

