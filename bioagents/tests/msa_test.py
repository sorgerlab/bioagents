import re
from time import sleep

from bioagents.msa import msa_module
from kqml.kqml_list import KQMLList
from bioagents.tests.util import ekb_from_text, get_request
from bioagents.tests.integration import _IntegrationTest
from nose.plugins.skip import SkipTest
from nose.plugins.attrib import attr


if not msa_module.CAN_CHECK_STATEMENTS:
    raise SkipTest("Database web api is not available (%s)." %
                   msa_module.CAN_CHECK_STATEMENTS)


def _get_message(heading, target=None, residue=None, position=None):
    msa = msa_module.MSA_Module(testing=True)
    content = KQMLList(heading)
    if target is not None:
        content.sets('target', ekb_from_text(target))
    if residue and position:
        content.sets('site', '%s-%s' % (residue, position))
    return msa.respond_phosphorylation_activating(content)


def _check_failure(msg, flaw, reason):
    assert msg.head() == 'FAILURE', \
        "MSA succeeded despite %s, giving %s" % (flaw, msg.to_string())
    assert msg.gets('reason') == reason


@attr('nonpublic')
def test_respond_phosphorylation_activating():
    "Test the msa_module response to a query regarding phosphorylation."
    msg = _get_message('PHOSPHORYLATION-ACTIVATING', 'MAP2K1', 'S', '222')
    assert msg.head() == 'SUCCESS', \
        "MSA could not perform this task because \"%s\"." % msg.gets('reason')
    assert msg.data[1].to_string() == ':is-activating', \
        'MSA responded with wrong topic \"%s\".' % msg.data[1].to_string()
    assert msg.data[2].to_string() == 'TRUE', \
        'MSA responded with wrong answer.'


@attr('nonpublic')
def test_no_target_failure():
    msg = _get_message('PHOSPHORYLATION-ACTIVATING')
    _check_failure(msg, 'no target given', 'MISSING_TARGET')


@attr('nonpublic')
def test_invalid_target_failure():
    msg = _get_message('PHOSPHORYLATION-ACTIVATING', 'JUND')
    _check_failure(msg, 'missing mechanism', 'MISSING_MECHANISM')


@attr('nonpublic')
def test_not_phosphorylation():
    msg = _get_message('BOGUS-ACTIVATING', 'MAP2K1', 'S', '222')
    _check_failure(msg, 'getting a bogus action', 'MISSING_MECHANISM')


@attr('nonpublic')
def test_not_activating():
    msg = _get_message('PHOSPHORYLATION-INHIBITING', 'MAP2K1', 'S', '222')
    _check_failure(msg, 'getting inhibition instead of activation',
                   'MISSING_MECHANISM')


@attr('nonpublic')
def test_no_activity_given():
    msg = _get_message('')
    _check_failure(msg, 'getting no activity type', 'UNKNOWN_ACTION')


class _TestMsaGeneralLookup(_IntegrationTest):
    def __init__(self, *args, **kwargs):
        super(_TestMsaGeneralLookup, self).__init__(msa_module.MSA_Module)

    def _get_content(self, task, **contents):
        content = KQMLList(task)
        for key, value in contents.items():
            content.set(key, value)
        msg = get_request(content)
        return msg, content

    def _get_tells(self, logs):
        return [msg for msg in logs if msg.head() == 'tell']

    def _get_provenance_tells(self, logs):
        provenance_tells = []
        for msg in logs:
            if msg.head() == 'tell' and msg.get('content'):
                content = msg.get('content')
                if content.head() == 'add-provenance':
                    html = content.gets('html')
                    provenance_tells.append(html.splitlines()[0])
        return provenance_tells

    def _check_find_response(self, output):
        assert output.head() == 'SUCCESS', str(output)
        t = 200
        prov_tells = []
        while t > 0 and not prov_tells:
            sleep(1)
            logs = self.get_output_log()
            prov_tells = self._get_provenance_tells(logs)
            t -= 1
        assert len(prov_tells) == 1, prov_tells
        if t < 50:
            print("WARNING: Provenance took more than 10 seconds to post.")


@attr('nonpublic')
class TestMSATypeAndTargetBRAF(_TestMsaGeneralLookup):
    def create_type_and_target(self):
        return self._get_content('FIND-RELATIONS-FROM-LITERATURE',
                                 source=ekb_from_text('None'),
                                 type='Phosphorylation',
                                 target=ekb_from_text('BRAF'))

    def check_response_to_type_and_target(self, output):
        return self._check_find_response(output)


@attr('nonpublic')
class TestMSATypeAndSourceBRAF(_TestMsaGeneralLookup):
    def create_type_and_source(self):
        return self._get_content('FIND-RELATIONS-FROM-LITERATURE',
                                 type='Phosphorylation',
                                 source=ekb_from_text('BRAF'),
                                 target=ekb_from_text('None'))

    def check_response_to_type_and_source(self, output):
        return self._check_find_response(output)


@attr('nonpublic')
class TestMSATypeAndTargetTP53(_TestMsaGeneralLookup):
    def create_type_and_source(self):
        return self._get_content('FIND-RELATIONS-FROM-LITERATURE',
                                 type='Phosphorylation',
                                 source=ekb_from_text('None'),
                                 target=ekb_from_text('TP53'))

    def check_response_to_type_and_source(self, output):
        return self._check_find_response(output)


@attr('nonpublic')
class TestMSAConfirm1(_TestMsaGeneralLookup):
    def create_message(self):
        return self._get_content('CONFIRM-RELATION-FROM-LITERATURE',
                                 type='phosphorylation',
                                 source=ekb_from_text('MEK'),
                                 target=ekb_from_text('ERK'))

    def check_response_to_message(self, output):
        return self._check_find_response(output)


@attr('nonpublic')
class TestMSAConfirm2(_TestMsaGeneralLookup):
    def create_message(self):
        return self._get_content('CONFIRM-RELATION-FROM-LITERATURE',
                                 type='phosphorylation',
                                 source=ekb_from_text('MAP2K1'),
                                 target=ekb_from_text('MAPK1'))

    def check_response_to_message(self, output):
        return self._check_find_response(output)


@attr('nonpublic')
class TestMsaPaperGraph(_IntegrationTest):
    def __init__(self, *args, **kwargs):
        super(TestMsaPaperGraph, self).__init__(msa_module.MSA_Module)

    def _is_sbgn(self, tell):
        content = tell.get('content')
        if not content:
            return False
        header = content.head()
        graph_type = content.gets('type')
        graph = content.gets('graph')
        if 'xmlns' not in graph or 'glyph' not in graph:
            return False
        return header == 'display-sbgn' and graph_type == 'sbgn'

    def create_message(self):
        content = KQMLList('GET-PAPER-MODEL')
        content.set('pmid', 'PMID-27906130')
        return get_request(content), content

    def check_response_to_message(self, output):
        logs = self.get_output_log()
        tells = [msg for msg in logs if msg.head() == 'tell']
        assert tells
        assert any([self._is_sbgn(tell) for tell in tells]),\
            "No recognized display commands."
        return


@attr('nonpublic')
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
        return msg, content

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
        evs = re.findall('<li>(.*?) \((\d+)\)</li>',
                         html_str)
        assert len(evs),\
            ("unexpectedly formatted provenance (got no regex extractions): %s"
             % html_str)
        # TODO: think of some way to test this better.
        return


@attr('nonpublic')
class TestMsaCommonUpstreamsMEKERK(_IntegrationTest):
    def __init__(self, *args, **kwargs):
        super(TestMsaCommonUpstreamsMEKERK, self).__init__(
            msa_module.MSA_Module)

    def create_message(self):
        content = KQMLList('GET-COMMON')
        ekb = ekb_from_text('MEK, ERK')
        content.sets('genes', ekb)
        content.sets('up-down', 'ONT::MORE')
        msg = get_request(content)
        return msg, content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('prefix') == 'up', output.gets('prefix')
        gene_list = output.get('commons')
        assert gene_list, output
        assert 'EGF' in gene_list, gene_list
        assert 'BRAF' in gene_list, gene_list


@attr('nonpublic')
class TestMsaCommonDownstreamsMEKERK(_IntegrationTest):
    def __init__(self, *args, **kwargs):
        super(TestMsaCommonDownstreamsMEKERK, self).__init__(
            msa_module.MSA_Module)

    def create_message(self):
        content = KQMLList('GET-COMMON')
        ekb = ekb_from_text('MEK, ERK')
        content.sets('genes', ekb)
        content.sets('up-down', 'ONT::SUCCESSOR')
        msg = get_request(content)
        return msg, content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('prefix') == 'down', output.gets('prefix')
        gene_list = output.get('commons')
        assert gene_list, output
        assert 'EGF' in gene_list, gene_list
        assert 'TNF' in gene_list, gene_list


@attr('nonpublic')
class TestMsaCommonUpstreamsTP53AKT1(_IntegrationTest):
    def __init__(self, *args, **kwargs):
        super(TestMsaCommonUpstreamsTP53AKT1, self).__init__(
            msa_module.MSA_Module)

    def create_message(self):
        content = KQMLList('GET-COMMON')
        ekb = ekb_from_text('TP53, AKT1')
        content.sets('genes', ekb)
        content.sets('up-down', 'ONT::MORE')
        msg = get_request(content)
        return msg, content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('prefix') == 'up', output.gets('prefix')
        gene_list = output.get('commons')
        assert gene_list, output
        assert 'PRKDC' in gene_list, gene_list
        assert 'ROS1' in gene_list, gene_list


@attr('nonpublic')
class TestMsaCommonDownstreamsTP53AKT1(_IntegrationTest):
    def __init__(self, *args, **kwargs):
        super(TestMsaCommonDownstreamsTP53AKT1, self).__init__(
            msa_module.MSA_Module)

    def create_message(self):
        content = KQMLList('GET-COMMON')
        ekb = ekb_from_text('TP53, AKT1')
        content.sets('genes', ekb)
        content.sets('up-down', 'ONT::SUCCESSOR')
        msg = get_request(content)
        return msg, content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('prefix') == 'down', output.gets('prefix')
        gene_list = output.get('commons')
        assert gene_list, output
        assert 'ROS1' in gene_list, gene_list
        assert 'CDKN1A' in gene_list, gene_list


@attr('nonpublic')
class TestMsaCommonDownstreamsMEKVemurafenib(_IntegrationTest):
    def __init__(self, *args, **kwargs):
        super(TestMsaCommonDownstreamsMEKVemurafenib, self).__init__(
            msa_module.MSA_Module)

    def create_message(self):
        content = KQMLList('GET-COMMON')
        ekb = ekb_from_text('MEK, Vemurafenib')
        content.sets('genes', ekb)
        content.sets('up-down', 'ONT::SUCCESSOR')
        msg = get_request(content)
        return msg, content

    def check_response_to_message(self, output):
        assert output.head() == 'FAILURE', output
        assert output.gets('reason') == 'MISSING_TARGET', output.gets('reason')


@attr('nonpublic')
class TestMsaCommonDownstreamsMEKonly(_IntegrationTest):
    def __init__(self, *args, **kwargs):
        super(TestMsaCommonDownstreamsMEKonly, self).__init__(
            msa_module.MSA_Module)

    def create_message(self):
        content = KQMLList('GET-COMMON')
        ekb = ekb_from_text('MEK')
        content.sets('genes', ekb)
        content.sets('up-down', 'ONT::SUCCESSOR')
        msg = get_request(content)
        return msg, content

    def check_response_to_message(self, output):
        assert output.head() == 'FAILURE', output
        assert output.gets('reason') == 'NO_TARGET', output.gets('reason')


@attr('nonpublic')
def test_msa_paper_retrieval_failure():
    raise SkipTest("This feature is currently not available.")
    content = KQMLList('GET-PAPER-MODEL')
    content.sets('pmid', 'PMID-00000123')
    msa = msa_module.MSA_Module(testing=True)
    resp = msa.respond_get_paper_model(content)
    assert resp.head() == 'FAILURE', str(resp)
    assert resp.get('reason') == 'MISSING_MECHANISM'
