import re
from bioagents.msa import msa_module
from kqml.kqml_list import KQMLList
from bioagents.tests.util import ekb_from_text, get_request
from bioagents.tests.integration import _IntegrationTest
from nose.plugins.skip import SkipTest


if not msa_module.CAN_CHECK_STATEMENTS:
    raise SkipTest("Database web api is not available.")


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


class TestMsaProvenance(_IntegrationTest):
    """Test that TRA can correctly run a model."""
    def __init__(self, *args, **kwargs):
        super(TestMsaProvenance, self).__init__(msa_module.MSA_Module)

    def create_message(self):
        content = KQMLList('PHOSPHORYLATION-ACTIVATING')
        content.sets('target', ekb_from_text('MAPK1'))
        for name, value in [('residue', 'T'), ('position', '185')]:
            if value is not None:
                content.sets(name, value)
        msg = get_request(content)
        return (msg, content)

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS',\
            'Query failed: %s.' % output.to_string()
        assert output.get('is-activating') == 'TRUE',\
            'Wrong result: %s.' % output.to_string()
        logs = self.get_output_log()
        provs = [msg for msg in logs
                if msg.head() == 'tell'
                and msg.get('content').head() == 'add-provenance']
        assert len(provs) == 1, 'Too much provenance: %d vs. 1.' % len(provs)
        html = provs[0].get('content').get('html')
        html_str = html.to_string()
        evs = re.findall("<i>[\"\'](.*?)[\"\']</i>.*?<a.*?>(?:pmid|PMID)(\d+)</a>",
                         html_str)
        evs += re.findall("<li>(.*?):.*?\(<a.*?>PMID(\d+)</a>\)</li>", html_str)
        assert len(evs),\
            ("unexpectedly formatted provenance (got no regex extractions): %s"
             % html_str)
        ev_counts = [(ev, evs.count(ev)) for ev in set(evs)]
        ev_duplicates = ['%d x \"%s\" with pmid %s' % (num, ev_str, pmid)
                         for (ev_str, pmid), num in ev_counts if num > 1]
        assert not ev_duplicates,\
            ("Some evidence listed multiple times:\n    %s\nFull html:\n%s"
             % ('\n    '.join(ev_duplicates), html.to_string()))
        return
