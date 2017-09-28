from kqml import KQMLList
from bioagents.dtda import DTDA
from bioagents.dtda import DTDA_Module
from tests.util import *
from tests.integration import _IntegrationTest, _FailureTest


def test_mutation_statistics():
    d = DTDA()
    mutation_dict = \
        d.get_mutation_statistics('pancreatic carcinoma', 'missense')
    assert(mutation_dict['KRAS'] > 0)


# FIND-TARGET-DRUG tests

class _TestFindTargetDrug(_IntegrationTest):
    def __init__(self, *args):
        super(_TestFindTargetDrug, self).__init__(DTDA_Module)

    def get_message(self):
        target = ekb_kstring_from_text(self.target)
        content = KQMLList('FIND-TARGET-DRUG')
        content.set('target', target)
        return get_request(content), content

    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        assert len(self.output.get('drugs')) == 9, self.output
        return True

    def give_feedback(self):
        return None


class TestFindTargetDrug1(_TestFindTargetDrug):
    target = 'BRAF'
    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        assert len(self.output.get('drugs')) == 9, self.output
        return True


class TestFindTargetDrug2(_TestFindTargetDrug):
    target = 'PAK4'
    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        assert len(self.output.get('drugs')) == 1, self.output
        assert self.output.get('drugs')[0].gets('name') == 'PF-3758309'
        assert self.output.get('drugs')[0].get('pubchem_id') == 25227462
        return True


class TestFindTargetDrug3(_TestFindTargetDrug):
    target = 'KRAS'
    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        assert len(self.output.get('drugs')) == 0, self.output
        return True


class TestFindTargetDrug4(_TestFindTargetDrug):
    target = 'JAK2'
    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        assert len(self.output.get('drugs')) == 3, self.output
        return True


# FIND-DRUG-TARGETS tests

class TestFindDrugTargets1(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def get_message(self):
        drug = ekb_kstring_from_text('Vemurafenib')
        content = KQMLList('FIND-DRUG-TARGETS')
        content.set('drug', drug)
        return get_request(content), content

    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        return True

    def give_feedback(self):
        return None


# IS-DRUG-TARGET tests

class _TestIsDrugTarget(_IntegrationTest):
    def __init__(self, *args):
        super(_TestIsDrugTarget, self).__init__(DTDA_Module)

    def get_message(self):
        target = ekb_kstring_from_text(self.target)
        drug = ekb_kstring_from_text(self.drug)
        content = KQMLList('IS-DRUG-TARGET')
        content.set('target', target)
        content.set('drug', drug)
        return get_request(content), content

    def give_feedback(self):
        return None

class TestIsDrugTarget1(_TestIsDrugTarget):
    target = 'BRAF'
    drug = 'Vemurafenib'
    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        assert self.output.gets('is-target') == 'TRUE', self.output
        return True

class TestIsDrugTarget2(_TestIsDrugTarget):
    target = 'BRAF'
    drug = 'dabrafenib'
    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        assert self.output.gets('is-target') == 'TRUE', self.output
        return True

class TestIsDrugTarget3(_TestIsDrugTarget):
    target = 'KRAS'
    drug = 'dabrafenib'
    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        assert self.output.gets('is-target') == 'FALSE', self.output
        return True


# FIND-TREATMENT tests

class TestFindDiseaseTargets1(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def get_message(self):
        disease = ekb_kstring_from_text('pancreatic cancer')
        content = KQMLList('FIND-DISEASE-TARGETS')
        content.set('disease', disease)
        return get_request(content), content

    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        assert len(self.output.get('drugs')) == 0, self.output
        return True

    def give_feedback(self):
        return None

class TestFindDiseaseTargets2(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def get_message(self):
        disease = ekb_kstring_from_text('lung cancer')
        content = KQMLList('FIND-DISEASE-TARGETS')
        content.set('disease', disease)
        return get_request(content), content

    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        assert self.output.gets('prevalence') == '0.19'
        assert self.output.gets('functional-effect') == 'ACTIVE'
        return True

    def give_feedback(self):
        return None

class TestFindDiseaseTargets3(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def get_message(self):
        disease = ekb_kstring_from_text('common cold')
        content = KQMLList('FIND-DISEASE-TARGETS')
        content.set('disease', disease)
        return get_request(content), content

    def is_correct_response(self):
        assert self.output.head() == 'FAILURE', self.output
        assert self.output.gets('reason') == 'DISEASE_NOT_FOUND', self.output
        return True

    def give_feedback(self):
        return None


# FIND-DISEASE-TARGETS tests

class TestFindTreatment1(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def get_message(self):
        disease = ekb_kstring_from_text('pancreatic cancer')
        content = KQMLList('FIND-TREATMENT')
        content.set('disease', disease)
        return get_request(content), content

    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        assert len(self.output.get('drugs')) == 0, self.output
        return True

    def give_feedback(self):
        return None

class TestFindTreatment2(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def get_message(self):
        disease = ekb_kstring_from_text('lung cancer')
        content = KQMLList('FIND-TREATMENT')
        content.set('disease', disease)
        return get_request(content), content

    def is_correct_response(self):
        part1, part2 = self.output
        assert part1.head() == 'SUCCESS', part1
        assert part2.head() == 'SUCCESS', part2
        assert part1.gets('prevalence') == '0.19', part1.get('prevalence')
        assert len(part2.get('drugs')) == 0
        return True

    def give_feedback(self):
        return None

class TestFindTreatment3(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def get_message(self):
        disease = ekb_kstring_from_text('common cold')
        content = KQMLList('FIND-TREATMENT')
        content.set('disease', disease)
        return get_request(content), content

    def is_correct_response(self):
        assert self.output.head() == 'FAILURE', self.output
        assert self.output.gets('reason') == 'DISEASE_NOT_FOUND', self.output
        return True

    def give_feedback(self):
        return None

