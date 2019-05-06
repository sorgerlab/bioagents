import re
from time import sleep
from nose.plugins.attrib import attr
from nose.plugins.skip import SkipTest

from bioagents import Bioagent
from bioagents.msa.msa import MSA
from indra.statements import Agent

from kqml.kqml_list import KQMLList

from bioagents.msa import msa, msa_module
from bioagents.tests.util import ekb_from_text, get_request
from bioagents.tests.integration import _IntegrationTest


if not msa_module.CAN_CHECK_STATEMENTS:
    raise SkipTest("Database web api is not available (%s)." %
                   msa_module.CAN_CHECK_STATEMENTS)


def _get_message(heading, target=None, residue=None, position=None):
    msa = msa_module.MSA_Module(testing=True)
    content = KQMLList(heading)
    if target is not None:
        content.sets('target', target)
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
    msg = _get_message('PHOSPHORYLATION-ACTIVATING', _MAP2K1(), 'S', '222')
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
    msg = _get_message('PHOSPHORYLATION-ACTIVATING', _JUND())
    _check_failure(msg, 'missing mechanism', 'MISSING_MECHANISM')


@attr('nonpublic')
def test_not_phosphorylation():
    msg = _get_message('BOGUS-ACTIVATING', _MAP2K1(), 'S', '222')
    _check_failure(msg, 'getting a bogus action', 'MISSING_MECHANISM')


@attr('nonpublic')
def test_not_activating():
    msg = _get_message('PHOSPHORYLATION-INHIBITING', _MAP2K1(), 'S', '222')
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


def _BRAF():
    return Bioagent.make_cljson(Agent('BRAF', db_refs={'HGNC': '1097'}))


def _TP53():
    return Bioagent.make_cljson(Agent('TP53', db_refs={'HGNC': '11998'}))


def _MEK():
    return Bioagent.make_cljson(Agent('MEK', db_refs={'FPLX': 'MEK'}))


def _ERK():
    return Bioagent.make_cljson(Agent('ERK', db_refs={'FPLX': 'ERK'}))


def _MAPK1():
    return Bioagent.make_cljson(Agent('MAPK1', db_refs={'HGNC': '6871'}))


def _MAP2K1():
    return Bioagent.make_cljson(Agent('MAP2K1', db_refs={'HGNC': '6840'}))


def _AKT1():
    return Bioagent.make_cljson(Agent('AKT1', db_refs={'HGNC': '391'}))


def _JUND():
    return Bioagent.make_cljson(Agent('JUND', db_refs={'HGNC': '6206'}))


def _Vemurafenib():
    return Bioagent.make_cljson(Agent('Vemurafenib',
                                      db_refs={'CHEBI': 'CHEBI:63637'}))


def _NONE():
    return KQMLList()


@attr('nonpublic')
class TestMSATypeAndTargetBRAF(_TestMsaGeneralLookup):
    def create_type_and_target(self):
        return self._get_content('FIND-RELATIONS-FROM-LITERATURE',
                                 source=_NONE(),
                                 type='Phosphorylation',
                                 target=_BRAF())

    def check_response_to_type_and_target(self, output):
        return self._check_find_response(output)


@attr('nonpublic')
class TestMSATypeAndSourceBRAF(_TestMsaGeneralLookup):
    def create_type_and_source(self):
        return self._get_content('FIND-RELATIONS-FROM-LITERATURE',
                                 type='Phosphorylation',
                                 source=_BRAF(),
                                 target=_NONE())

    def check_response_to_type_and_source(self, output):
        return self._check_find_response(output)


@attr('nonpublic')
class TestMSATypeAndTargetTP53(_TestMsaGeneralLookup):
    def create_type_and_source(self):
        return self._get_content('FIND-RELATIONS-FROM-LITERATURE',
                                 type='Phosphorylation',
                                 source=_NONE(),
                                 target=_TP53())

    def check_response_to_type_and_source(self, output):
        return self._check_find_response(output)


@attr('nonpublic')
class TestMSAConfirm1(_TestMsaGeneralLookup):
    def create_message(self):
        return self._get_content('CONFIRM-RELATION-FROM-LITERATURE',
                                 type='phosphorylation',
                                 source=_MEK(),
                                 target=_ERK())

    def check_response_to_message(self, output):
        return self._check_find_response(output)


@attr('nonpublic')
class TestMSAConfirm2(_TestMsaGeneralLookup):
    def create_message(self):
        return self._get_content('CONFIRM-RELATION-FROM-LITERATURE',
                                 type='phosphorylation',
                                 source=_MAP2K1(),
                                 target=_MAPK1())

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
        content.sets('target', _MAPK1())
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
        content.set('genes', KQMLList([_MEK(), _ERK()]))
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
        content.set('genes', KQMLList([_MEK(), _ERK()]))
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
        content.set('genes', KQMLList([_TP53(), _AKT1()]))
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
        content.set('genes', KQMLList([_TP53(), _AKT1()]))
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
        content.set('genes', KQMLList([_MEK(), _Vemurafenib()]))
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
        content.set('genes', KQMLList([_MEK()]))
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


@attr('nonpublic')
def test_valid_keys_no_text():
    # We test that an agent with just a PUBCHEM ID can still be queried
    msa = MSA()
    ag = Agent('vemurafenib', db_refs={'PUBCHEM': '42611257'})
    finder = msa.find_mechanisms('from_source', ag)
    stmts = finder.get_statements(block=True)
    assert stmts


@attr('nonpublic')
def test_get_finder_agents():
    msa = MSA()
    ag = Agent('SOCS1', db_refs={'HGNC': '19383'})
    finder = msa.find_mechanisms('to_target', ag, verb='phosphorylate')
    other_agents = finder.get_other_agents()
    assert all(isinstance(a, Agent) for a in other_agents)

    fixed_agents = finder.get_fixed_agents()
    assert 'object' in fixed_agents, fixed_agents
    assert fixed_agents['object'][0].name == 'SOCS1', fixed_agents['target']

    # The other names should be sorted with PIM1 first (most evidence)
    other_names = finder.get_other_names(ag)
    assert other_names[0] == 'PIM1', other_names


@attr('nonpublic')
def test_activeform_finder_get_agents():
    finder = msa.Activeforms(Agent('MEK', db_refs={'FPLX': 'MEK'}))
    fa = finder.get_fixed_agents()
    assert set(fa.keys()) == {'other'}, fa
    assert len(fa['other']) == 1, len(fa['other'])
    assert fa['other'][0].name == 'MEK', fa['other'][0]
    oa = finder.get_other_agents(block=True)
    assert len(oa) == 0, len(oa)


@attr('nonpublic')
def test_commons_finder_get_agents():
    finder = msa.CommonDownstreams(Agent('MEK', db_refs={'FPLX': 'MEK'}),
                                   Agent('RAF', db_refs={'FPLX': 'RAF'}))
    fa = finder.get_fixed_agents()
    assert set(fa.keys()) == {'other'}, fa
    assert len(fa['other']) == 2, len(fa['other'])
    assert {ag.name for ag in fa['other']} == {'MEK', 'RAF'}

    oa = finder.get_other_agents(block=True)
    assert len(oa) > 3


@attr('nonpublic')
def test_to_target_ERK():
    finder = msa.ToTarget(Agent('ERK', db_refs={'FPLX': 'ERK'}), persist=False)
    stmts = finder.get_statements(block=True)
    assert not any(None in s.agent_list() for s in stmts), stmts


@attr('nonpublic')
def test_to_target_entity_filter():
    # Kinases
    finder = msa.ToTarget(Agent('MEK', db_refs={'FPLX': 'MEK'}),
                          ent_type='kinase', persist=False)
    oa = finder.get_other_agents(block=True)
    oa_names = [a.name for a in oa]
    # RAF1 as a kinase is in the list
    assert 'RAF1' in oa_names
    # RAS, which normally is in the list should not be since it's not a kinase
    assert 'RAS' not in oa_names
    assert 'ESR1' not in oa_names

    # Transcription factors
    finder = msa.ToTarget(Agent('MEK', db_refs={'FPLX': 'MEK'}),
                          ent_type='transcription factor', persist=False)
    oa = finder.get_other_agents(block=True)
    oa_names = [a.name for a in oa]
    assert 'ESR1' in oa_names
    assert 'RAF1' not in oa_names

    # Proteins
    finder = msa.ToTarget(Agent('MEK', db_refs={'FPLX': 'MEK'}),
                          ent_type='protein', persist=False)
    oa = finder.get_other_agents(block=True)
    oa_names = [a.name for a in oa]
    assert 'ESR1' in oa_names
    assert 'RAF1' in oa_names
    assert 'U0126' not in oa_names
    assert 'trametinib' not in oa_names


@attr('nonpublic')
def test_from_source_entity_filter():
    # Kinases
    finder = msa.FromSource(Agent('MEK', db_refs={'FPLX': 'MEK'}),
                            ent_type='kinase', persist=False)
    oa = finder.get_other_agents(block=True)
    oa_names = [a.name for a in oa]
    # RAF1 as a kinase is in the list
    assert 'MAPK1' in oa_names
    # RAS, which normally is in the list should not be since it's not a kinase
    assert 'apoptosis' not in oa_names
    assert 'RAS' not in oa_names

    # Transcription factors
    finder = msa.FromSource(Agent('MEK', db_refs={'FPLX': 'MEK'}),
                            ent_type='transcription factor', persist=False)
    oa = finder.get_other_agents(block=True)
    oa_names = [a.name for a in oa]
    assert 'ESR1' in oa_names
    assert 'RAF1' not in oa_names

    # Proteins
    finder = msa.FromSource(Agent('MEK', db_refs={'FPLX': 'MEK'}),
                            ent_type='protein', persist=False)
    oa = finder.get_other_agents(block=True)
    oa_names = [a.name for a in oa]
    assert 'ERK' in oa_names
    assert 'MAPK1' in oa_names
    assert 'apoptosis' not in oa_names
    assert 'proliferation' not in oa_names


def _braf():
    return Agent('BRAF', db_refs={'HGNC': '1097'})


def _kras():
    return Agent('KRAS', db_refs={'HGNC': '6407'})


def _mek():
    return Agent('MEK', db_refs={'FPLX': 'MEK'})


def _erk():
    return Agent('ERK', db_refs={'FPLX': 'ERK'})


@attr('nonpublic')
def test_complex_one_side_entity_filter():
    finder = msa.ComplexOneSide(_braf(), persist=False)
    oa = finder.get_other_agents(block=True)
    oa_names = [a.name for a in oa]
    # Make sure we can get the query entity itself if it's another member of
    # the complex
    assert 'BRAF' in oa_names

    # Phosphatases
    finder = msa.ComplexOneSide(_braf(), ent_type='phosphatase', persist=False)
    oa = finder.get_other_agents(block=True)
    oa_names = [a.name for a in oa]
    assert 'RAF1' not in oa_names
    assert 'PTEN' in oa_names
    assert 'BRAF' not in oa_names


@attr('nonpublic')
def test_neighbors_agent_filter():
    finder = msa.Neighborhood(_braf(), filter_agents=[_mek(), _erk()])
    stmts = finder.get_statements(block=True)
    assert len(stmts)
    for stmt in stmts:
        ag_names = {ag.name for ag in stmt.agent_list() if ag is not None}
        assert ag_names & {'ERK', 'MEK'}


@attr('nonpublic')
def test_upstreams_agent_filter():
    finder = msa.CommonUpstreams(_mek(), _erk(),
                                 filter_agents=[_braf(), _kras()])
    stmts = finder.get_statements(block=True)
    assert len(stmts)
    exp_ags = {'BRAF', 'KRAS'}
    for stmt in stmts:
        ag_names = {ag.name for ag in stmt.agent_list() if ag is not None}
        assert ag_names & exp_ags, ag_names - exp_ags - {'MEK', 'ERK'}


@attr('nonpublic', 'slow')
def test_to_target_agent_filter():
    finder = msa.ToTarget(_erk(), filter_agents=[_mek(), _braf(), _kras()])
    stmts = finder.get_statements()
    assert len(stmts)
    exp_ags = {'MEK', 'BRAF', 'KRAS'}
    for stmt in stmts:
        ag_names = {ag.name for ag in stmt.agent_list() if ag is not None}
        assert ag_names & exp_ags, ag_names - exp_ags - {'ERK'}


@attr('nonpublic', 'slow')
def test_to_target_agent_filter():
    finder = msa.FromSource(_erk(), filter_agents=[_mek(), _braf(), _erk()])
    stmts = finder.get_statements()
    assert len(stmts)
    exp_ags = {'MEK', 'BRAF', 'KRAS', 'ERK'}
    for stmt in stmts:
        ag_names = {ag.name for ag in stmt.agent_list() if ag is not None}
        assert ag_names & exp_ags, ag_names - exp_ags
