from bioagents.msa import msa_module
from kqml.kqml_list import KQMLList
from tests.util import ekb_from_text


def _get_message(heading, target=None, residue=None, position=None):
    msa = msa_module.MSA_Module(testing=True)
    content = KQMLList(heading)
    if target is not None:
        content.sets('target', ekb_from_text(target))
    for name, value in [('residue', residue), ('position', position)]:
        if value is not None:
            content.sets(name, value)
    return msa.respond_phosphorylation_activating(content)


def _check_failure(msg, flaw, reason):
    assert msg.head() == 'FAILURE', \
        "MSA succeeded despite %s, giving %s" % (flaw, msg.to_string())
    assert msg.gets('reason') == reason


def test_respond_phosphorylation_activating():
    "Test the msa_module response to a query regarding phosphorylation."
    msg = _get_message('PHOSPHORYLATION-ACTIVATING', 'MAP2K1', 'S', '222')
    assert msg.head() == 'SUCCESS', \
        "MSA could not perform this task because \"%s\"." % msg.gets('reason')
    assert msg.data[1].to_string() == ':is-activating', \
        'MSA responded with wrong topic \"%s\".' % msg.data[1].to_string()
    assert msg.data[2].to_string() == 'TRUE', \
        'MSA responded with wrong answer.'


def test_no_target_failure():
    msg = _get_message('PHOSPHORYLATION-ACTIVATING')
    _check_failure(msg, 'no target given', 'MISSING_TARGET')


def test_invalid_target_failure():
    msg = _get_message('PHOSPHORYLATION-ACTIVATING', 'MEK')
    _check_failure(msg, 'missing mechanism', 'MISSING_MECHANISM')


def test_not_phosphorylation():
    msg = _get_message('BOGUS-ACTIVATING', 'MAP2K1', 'S', '222')
    _check_failure(msg, 'getting a bogus action', 'MISSING_MECHANISM')


def test_not_activating():
    msg = _get_message('PHOSPHORYLATION-INHIBITING', 'MAP2K1', 'S', '222')
    _check_failure(msg, 'getting inhibition instead of activation',
                   'MISSING_MECHANISM')


def test_no_activity_given():
    msg = _get_message('')
    _check_failure(msg, 'getting no activity type', 'UNKNOWN_ACTION')
