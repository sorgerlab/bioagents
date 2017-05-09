from kqml import KQMLList
from bioagents.dtda import DTDA
from bioagents.dtda import DTDA_Module

def test_mutation_statistics():
    d = DTDA()
    mutation_dict = \
        d.get_mutation_statistics('pancreatic carcinoma', 'missense')
    assert(mutation_dict['KRAS'] > 0)

def test_is_drug_target():
    req = '(IS-DRUG-TARGET :DRUG "<TERM id=\\"V33937\\" dbid=\\"CHEBI:63637\\"><features></features><type>ONT::MOLECULE</type><name>VEMURAFENIB</name><drum-terms><drum-term dbid=\\"CHEBI:63637\\" match-score=\\"1.0\\" name=\\"vemurafenib\\" /></drum-terms></TERM>" :TARGET "<TERM id=\\"V33952\\" dbid=\\"HGNC:1097|NCIT:C51194|NCIT:C17476\\"><features></features><type>ONT::GENE-PROTEIN</type><name>BRAF</name><drum-terms><drum-term dbid=\\"HGNC:1097\\" match-score=\\"0.99587\\" name=\\"B-Raf proto-oncogene, serine/threonine kinase\\" /><drum-term dbid=\\"NCIT:C51194\\" match-score=\\"0.99587\\" name=\\"BRAF\\" /><drum-term dbid=\\"NCIT:C17476\\" match-score=\\"0.82444\\" name=\\"B-RAF protein kinase\\" /></drum-terms></TERM>")'
    req_msg = KQMLList.from_string(req)
    dm = DTDA_Module(['-testing', 'true'])
    res = dm.respond_is_drug_target(req_msg)
    assert(res.to_string() == '(SUCCESS :is-target TRUE)')
