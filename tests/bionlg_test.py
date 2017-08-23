from kqml import KQMLList
from bioagents.bionlg import BioNLG_Module

def test_active_flag():
    kp = KQMLList.from_string('(INDRA-TO-NL :STATEMENTS "[{\\"obj\\": {\\"db_refs\\": {\\"TEXT\\": \\"MAP-2-K-1\\", \\"HGNC\\": \\"6840\\", \\"UP\\": \\"Q02750\\", \\"NCIT\\": \\"C17808\\"}, \\"name\\": \\"MAP2K1\\"}, \\"type\\": \\"Activation\\", \\"obj_activity\\": \\"activity\\", \\"evidence\\": [{\\"epistemics\\": {\\"section_type\\": null}, \\"source_api\\": \\"trips\\"}], \\"subj\\": {\\"activity\\": {\\"is_active\\": true, \\"activity_type\\": \\"activity\\"}, \\"db_refs\\": {\\"TEXT\\": \\"BRAF\\", \\"HGNC\\": \\"1097\\", \\"UP\\": \\"P15056\\", \\"NCIT\\": \\"C17476\\"}, \\"name\\": \\"BRAF\\"}, \\"id\\": \\"863fec09-025b-4e9b-8863-16e2601741d2\\"}]")')
    bn = BioNLG_Module(testing=True)
    res = bn.respond_indra_to_nl(kp)
    nl = res.get('NL')
    assert(len(nl) == 1)
    sentence = nl[0].string_value()
    assert(sentence == 'Active BRAF activates MAP2K1')
