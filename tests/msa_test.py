from bioagents.msa import msa_module
from kqml.kqml_list import KQMLList
from tests.util import ekb_from_text


def test_respond_phosphorylation_activating():
    "Test the msa_module response to a query regarding phosphorylation."
    msa = msa_module.MSA_Module(testing=True)
    content = KQMLList('PHOSPHORYLATION-ACTIVATING')
    content.sets('target', ekb_from_text('MAP2K1'))
    content.sets('residue', 'S')
    content.sets('position', '222')
    msg = msa.respond_phosphorylation_activating(content)
    assert msg.head() == 'SUCCESS',\
        "MSA could not perform this task because \"%s\"." % msg.gets('reason')
    assert msg.data[1].to_string() == ':is-activating',\
        'MSA responded with wrong topic \"%s\".' % msg.data[1].to_string()
    assert msg.data[2].to_string() == 'TRUE',\
        'MSA responded with wrong answer.'


def test_no_target_failure():
    msa = msa_module.MSA_Module(testing=True)
    content = KQMLList('PHOSPHORYLATION-ACTIVATING')
    msg = msa.respond_phosphorylation_activating(content)
    assert msg.head() == 'FAILURE',\
        "MSA found target when no target given, giving %s." % msg.to_string()


def test_invalid_target_failure():
    msa = msa_module.MSA_Module(testing=True)
    content = KQMLList('PHOSPHORYLATION-ACTIVATING')
    content.sets('target', ekb_from_text('MEK'))
    msg = msa.respond_phosphorylation_activating(content)
    assert msg.head() == 'FAILURE',\
        "MSA succeeded despite invalid target, giving %s." % msg.to_string()
