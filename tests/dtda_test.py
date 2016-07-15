from bioagents.trips.kqml_list import KQMLList
from bioagents.dtda import DTDA
from bioagents.dtda import DTDA_Module

def test_mutation_statistics():
    d = DTDA()
    mutation_dict = \
        d.get_mutation_statistics('pancreatic carcinoma', 'missense')
    assert(mutation_dict['KRAS'] > 0)

def test_get_disease():
    disease_str = '(CANCER :DBNAME "pancreatic carcinoma" :DBID "EFO:0002618")'
    kl = KQMLList.from_string(disease_str)
    disease = DTDA_Module.get_disease(kl)
    assert(disease.disease_type == 'cancer')
    assert(disease.name == 'pancreatic carcinoma')
    assert(disease.db_refs == {'EFO': '0002618'})
