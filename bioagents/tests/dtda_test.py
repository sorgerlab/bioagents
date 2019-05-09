import xml.etree.ElementTree as ET
from indra.statements import Agent
from kqml import KQMLList
from bioagents.dtda.dtda import DTDA, get_disease
from bioagents.dtda.dtda_module import DTDA_Module
from bioagents.tests.util import ekb_from_text, ekb_kstring_from_text, \
    get_request, agent_clj_from_text
from bioagents.tests.integration import _IntegrationTest
from nose.plugins.attrib import attr


# DTDA unit tests

@attr('nonpublic')
def test_mutation_statistics():
    d = DTDA()
    mutation_dict = \
        d.get_mutation_statistics('pancreatic carcinoma', 'missense')
    assert mutation_dict['KRAS']['count'] > 0


def test_get_disease():
    disease_ekb = ekb_from_text('pancreatic cancer')
    disease = get_disease(ET.fromstring(disease_ekb))
    disease_ekb = ekb_from_text('lung cancer')
    disease = get_disease(ET.fromstring(disease_ekb))
    disease_ekb = ekb_from_text('diabetes')
    disease = get_disease(ET.fromstring(disease_ekb))
    disease_ekb = ekb_from_text('common cold')
    disease = get_disease(ET.fromstring(disease_ekb))


def _create_agent(name, **refs):
    return Agent(name, db_refs={k.upper(): v for k, v in refs.items()})


_vems = [_create_agent('Vemurafenib', chebi='CHEBI:63637'),
         _create_agent('Vemurafenib', chebi='CHEBI:63637',
                       text='VEMURAFENIB')]
_alk_drug = _create_agent('SB-525334', pubchem='9967941', text='SB525334')
_braf = _create_agent('BRAF', hgnc='1097')
_kras = _create_agent('KRAS', hgnc='6407')
_tgfbr1 = _create_agent('TGFBR1', hgnc='11772')


@attr('nonpublic')
def test_is_nominal_target():
    d = DTDA()
    for vem in _vems:
        is_target = d.is_nominal_drug_target(vem, _braf)
        assert is_target
        is_target = d.is_nominal_drug_target(vem, _kras)
        assert not is_target


@attr('nonpublic')
def test_is_nominal_target_dash():
    d = DTDA()
    is_target = d.is_nominal_drug_target(_alk_drug, _tgfbr1)
    assert is_target


@attr('nonpublic')
def test_find_drug_targets1():
    d = DTDA()
    for vem in _vems:
        targets = d.find_drug_targets(vem)
        assert len(targets) >= 1, targets
        assert any(target == 'BRAF' for target in targets), targets


@attr('nonpublic')
def test_find_drug_targets2():
    d = DTDA()
    targets = d.find_drug_targets(_alk_drug)
    assert len(targets) == 1
    assert any(target == 'TGFBR1' for target in targets), targets


# FIND-TARGET-DRUG tests

class _TestFindTargetDrug(_IntegrationTest):
    def __init__(self, *args):
        super(_TestFindTargetDrug, self).__init__(DTDA_Module)

    def create_message(self):
        target = agent_clj_from_text(self.target)
        content = KQMLList('FIND-TARGET-DRUG')
        content.set('target', target)
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert len(output.get('drugs')) == 9, (len(output.get('drugs')), output)


@attr('nonpublic')
class TestFindTargetDrugBRAF(_TestFindTargetDrug):
    target = 'BRAF'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert len(output.get('drugs')) >= 9, (len(output.get('drugs')), output)


@attr('nonpublic')
class TestFindTargetDrugAKT(_TestFindTargetDrug):
    target = 'AKT'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert isinstance(output.get('drugs'), KQMLList), output.get('drugs')
        assert len(output.get('drugs')) == 0, (len(output.get('drugs')), output)


@attr('nonpublic')
class TestFindTargetDrugPAK4(_TestFindTargetDrug):
    target = 'PAK4'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        drugs = output.get('drugs')
        assert isinstance(output.get('drugs'), KQMLList), output.get('drugs')
        assert drugs, drugs
        assert len(drugs) >= 1, (len(drugs), drugs)
        drug_names = [drug.gets('name') for drug in drugs]
        exp_drug_name = 'PF-3758309'
        assert exp_drug_name in drug_names,\
            "Expected to find %s; not among %s." % (exp_drug_name, drug_names)
        pubchem_ids = []
        for drug in drugs:
            drug = self.bioagent.get_agent(drug)
            if drug.db_refs:
                pubchem_ids.append(drug.db_refs.get('PUBCHEM'))
        exp_pubchem_id = '25227462'
        assert exp_pubchem_id in pubchem_ids,\
            ("Got pubchem ids %s for drugs %s; expected to find id %s."
             % (pubchem_ids, drug_names, exp_pubchem_id))


@attr('nonpublic')
class TestFindTargetDrugKRAS(_TestFindTargetDrug):
    target = 'KRAS'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert len(output.get('drugs')) == 0, (len(output.get('drugs')), output)


@attr('nonpublic')
class TestFindTargetDrugJAK2(_TestFindTargetDrug):
    target = 'JAK2'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert len(output.get('drugs')) >= 9, (len(output.get('drugs')), output)


@attr('nonpublic')
class TestFindTargetDrugJAK1(_TestFindTargetDrug):
    target = 'JAK1'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert len(output.get('drugs')) >= 6, (len(output.get('drugs')), output)


# FIND-DRUG-TARGETS tests
@attr('nonpublic')
class TestFindDrugTargetsVemurafenib(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def create_message(self):
        drug = agent_clj_from_text('Vemurafenib')
        content = KQMLList('FIND-DRUG-TARGETS')
        content.set('drug', drug)
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        targets = output.get('targets')
        assert targets
        assert len(targets) >= 1, targets
        assert any(target.gets('name') == 'BRAF' for target in targets), targets


@attr('nonpublic')
class TestFindDrugTargetsSB525334(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def create_message(self):
        drug = agent_clj_from_text('SB525334')
        content = KQMLList('FIND-DRUG-TARGETS')
        content.set('drug', drug)
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert len(output.get('targets')) == 1, output
        assert output.get('targets')[0].gets('name') == 'TGFBR1'


# IS-DRUG-TARGET tests

class _TestIsDrugTarget(_IntegrationTest):
    target = NotImplemented
    drug = NotImplemented

    def __init__(self, *args):
        super(_TestIsDrugTarget, self).__init__(DTDA_Module)

    def create_message(self):
        target = self.bioagent.make_cljson(Agent(self.target))
        drug = self.bioagent.make_cljson(Agent(self.drug))
        content = KQMLList('IS-DRUG-TARGET')
        content.set('target', target)
        content.set('drug', drug)
        return get_request(content), content


@attr('nonpublic')
class TestIsDrugTarget1(_TestIsDrugTarget):
    target = 'BRAF'
    drug = 'Vemurafenib'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('is-target') == 'TRUE', output


@attr('nonpublic')
class TestIsDrugTargetMAP2K1Selumetinib(_TestIsDrugTarget):
    target = 'MAP2K1'
    drug = 'Selumetinib'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('is-target') == 'TRUE', output


@attr('nonpublic')
class TestIsDrugTarget2(_TestIsDrugTarget):
    target = 'BRAF'
    drug = 'dabrafenib'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('is-target') == 'TRUE', output


@attr('nonpublic')
class TestIsDrugTarget3(_TestIsDrugTarget):
    target = 'KRAS'
    drug = 'dabrafenib'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('is-target') == 'FALSE', output


@attr('nonpublic')
class TestIsDrugTarget4(_TestIsDrugTarget):
    target = 'TGFBR1'
    drug = 'SB525334'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('is-target') == 'TRUE', output


# FIND-DISEASE-TARGETS tests
@attr('nonpublic')
class TestFindDiseaseTargets1(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def create_message(self):
        disease = ekb_kstring_from_text('pancreatic cancer')
        content = KQMLList('FIND-DISEASE-TARGETS')
        content.set('disease', disease)
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        protein = output.get('protein')
        assert protein.get('name') == 'KRAS'
        assert 0.8 < float(output.gets('prevalence')) < 0.9,\
            output.gets('prevalence')
        assert output.gets('functional-effect') == 'ACTIVE'


@attr('nonpublic')
class TestFindDiseaseTargets2(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def create_message(self):
        disease = ekb_kstring_from_text('lung cancer')
        content = KQMLList('FIND-DISEASE-TARGETS')
        content.set('disease', disease)
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('prevalence') == '0.19'
        assert output.gets('functional-effect') == 'ACTIVE'


@attr('nonpublic')
class TestFindDiseaseTargets3(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def create_message(self):
        disease = ekb_kstring_from_text('common cold')
        content = KQMLList('FIND-DISEASE-TARGETS')
        content.set('disease', disease)
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'FAILURE', output
        assert output.gets('reason') == 'DISEASE_NOT_FOUND', output


# FIND-TREATMENT tests
@attr('nonpublic')
class TestFindTreatment1(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def create_message(self):
        disease = ekb_kstring_from_text('pancreatic cancer')
        content = KQMLList('FIND-TREATMENT')
        content.set('disease', disease)
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert 0.8 < float(output.gets('prevalence')) < 0.9, \
            output.get('prevalence')
        assert len(output.get('drugs')) == 0


@attr('nonpublic')
class TestFindTreatment2(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def create_message(self):
        disease = ekb_kstring_from_text('lung cancer')
        content = KQMLList('FIND-TREATMENT')
        content.set('disease', disease)
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('prevalence') == '0.19', output.get('prevalence')
        assert len(output.get('drugs')) == 0


@attr('nonpublic')
class TestFindTreatment3(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def create_message(self):
        disease = ekb_kstring_from_text('common cold')
        content = KQMLList('FIND-TREATMENT')
        content.set('disease', disease)
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'FAILURE', output
        assert output.gets('reason') == 'DISEASE_NOT_FOUND', output
