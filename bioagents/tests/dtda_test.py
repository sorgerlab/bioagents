from kqml import KQMLList
from bioagents.dtda.dtda import DTDA
from bioagents.dtda.dtda_module import DTDA_Module
from bioagents.tests.util import ekb_from_text, ekb_kstring_from_text, get_request
from bioagents.tests.integration import _IntegrationTest

# DTDA unit tests


def test_mutation_statistics():
    d = DTDA()
    mutation_dict = \
        d.get_mutation_statistics('pancreatic carcinoma', 'missense')
    assert(mutation_dict['KRAS'][0] > 0)


def test_get_disease():
    disease_ekb = ekb_from_text('pancreatic cancer')
    disease = DTDA_Module.get_disease(disease_ekb)
    disease_ekb = ekb_from_text('lung cancer')
    disease = DTDA_Module.get_disease(disease_ekb)
    disease_ekb = ekb_from_text('diabetes')
    disease = DTDA_Module.get_disease(disease_ekb)
    disease_ekb = ekb_from_text('common cold')
    disease = DTDA_Module.get_disease(disease_ekb)


def test_is_nominal_target():
    d = DTDA()
    vems = ('vemurafenib', 'Vemurafenib', 'VEMURAFENIB')
    for vem in vems:
        is_target = d.is_nominal_drug_target([vem], 'BRAF')
        assert is_target
        is_target = d.is_nominal_drug_target([vem], 'KRAS')
        assert not is_target


def test_is_nominal_target_dash():
    d = DTDA()
    is_target = d.is_nominal_drug_target(['SB525334', 'SB-525334'],
                                         'TGFBR1')
    assert is_target


def test_find_drug_targets1():
    d = DTDA()
    vems = ('vemurafenib', 'Vemurafenib', 'VEMURAFENIB')
    for vem in vems:
        targets = d.find_drug_targets(vem)
        assert len(targets) == 1
        assert targets[0] == 'BRAF', targets


def test_find_drug_targets2():
    d = DTDA()
    targets = d.find_drug_targets('SB525334')
    assert len(targets) == 1
    assert targets[0] == 'TGFBR1', targets


# FIND-TARGET-DRUG tests

class _TestFindTargetDrug(_IntegrationTest):
    def __init__(self, *args):
        super(_TestFindTargetDrug, self).__init__(DTDA_Module)

    def create_message(self):
        target = ekb_kstring_from_text(self.target)
        content = KQMLList('FIND-TARGET-DRUG')
        content.set('target', target)
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert len(output.get('drugs')) == 9, output


class TestFindTargetDrug1(_TestFindTargetDrug):
    target = 'BRAF'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert len(output.get('drugs')) == 9, output


class TestFindTargetDrug2(_TestFindTargetDrug):
    target = 'PAK4'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert len(output.get('drugs')) == 1, output
        drug_name = output.get('drugs')[0].gets('name')
        exp_drug_name = 'PF-3758309'
        assert drug_name == exp_drug_name,\
            "Got %s as drug name; expected %s." % (drug_name, exp_drug_name)
        pubchem_id = int(output.get('drugs')[0].get('pubchem_id').to_string())
        exp_pubchem_id = 25227462
        assert pubchem_id == exp_pubchem_id,\
            ("Got %d as pubchem id for %s; expected %d."
             % (pubchem_id, drug_name, exp_pubchem_id))


class TestFindTargetDrug3(_TestFindTargetDrug):
    target = 'KRAS'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert len(output.get('drugs')) == 0, output


class TestFindTargetDrug4(_TestFindTargetDrug):
    target = 'JAK2'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert len(output.get('drugs')) == 9, output


class TestFindTargetDrug5(_TestFindTargetDrug):
    target = 'JAK1'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert len(output.get('drugs')) == 6, output


# FIND-DRUG-TARGETS tests

class TestFindDrugTargets1(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def create_message(self):
        drug = ekb_kstring_from_text('Vemurafenib')
        content = KQMLList('FIND-DRUG-TARGETS')
        content.set('drug', drug)
        return get_request(content), content

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        targets = output.get('targets')
        assert targets
        assert len(targets) >= 3, targets
        assert any(target.gets('name') == 'BRAF' for target in targets), targets


class TestFindDrugTargets2(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def create_message(self):
        drug = ekb_kstring_from_text('SB525334')
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
        target = ekb_kstring_from_text(self.target)
        drug = ekb_kstring_from_text(self.drug)
        content = KQMLList('IS-DRUG-TARGET')
        content.set('target', target)
        content.set('drug', drug)
        return get_request(content), content


class TestIsDrugTarget1(_TestIsDrugTarget):
    target = 'BRAF'
    drug = 'Vemurafenib'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('is-target') == 'TRUE', output


class TestIsDrugTarget2(_TestIsDrugTarget):
    target = 'BRAF'
    drug = 'dabrafenib'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('is-target') == 'TRUE', output


class TestIsDrugTarget3(_TestIsDrugTarget):
    target = 'KRAS'
    drug = 'dabrafenib'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('is-target') == 'FALSE', output


class TestIsDrugTarget4(_TestIsDrugTarget):
    target = 'TGFBR1'
    drug = 'SB525334'

    def check_response_to_message(self, output):
        assert output.head() == 'SUCCESS', output
        assert output.gets('is-target') == 'TRUE', output


# FIND-DISEASE-TARGETS tests
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
class TestFindTreatment1(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def create_message(self):
        disease = ekb_kstring_from_text('pancreatic cancer')
        content = KQMLList('FIND-TREATMENT')
        content.set('disease', disease)
        return get_request(content), content

    def check_response_to_message(self, output):
        part1, part2 = output
        assert part1.head() == 'SUCCESS', part1
        assert part2.head() == 'SUCCESS', part2
        assert 0.8 < float(part1.gets('prevalence')) < 0.9, \
            part1.get('prevalence')
        assert len(part2.get('drugs')) == 0


class TestFindTreatment2(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def create_message(self):
        disease = ekb_kstring_from_text('lung cancer')
        content = KQMLList('FIND-TREATMENT')
        content.set('disease', disease)
        return get_request(content), content

    def check_response_to_message(self, output):
        part1, part2 = output
        assert part1.head() == 'SUCCESS', part1
        assert part2.head() == 'SUCCESS', part2
        assert part1.gets('prevalence') == '0.19', part1.get('prevalence')
        assert len(part2.get('drugs')) == 0


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


if __name__ == '__main__':
    TestFindDrugTargets2().run_test()
