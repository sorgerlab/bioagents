from kqml import KQMLList
from bioagents.dtda import DTDA
from bioagents.dtda import DTDA_Module
from tests.util import *
from tests.integration import _IntegrationTest, _FailureTest


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


class TestIsDrugTarget1(_IntegrationTest):
    def __init__(self, *args):
        super(self.__class__, self).__init__(DTDA_Module)

    def get_message(self):
        target = ekb_kstring_from_text('BRAF')
        drug = ekb_kstring_from_text('Vemurafenib')
        content = KQMLList('IS-DRUG-TARGET')
        content.set('target', target)
        content.set('drug', drug)
        return get_request(content), content

    def is_correct_response(self):
        assert self.output.head() == 'SUCCESS', self.output
        assert self.output.gets('is-target') == 'TRUE', self.output
        return True

    def give_feedback(self):
        return None


def test_mutation_statistics():
    d = DTDA()
    mutation_dict = \
        d.get_mutation_statistics('pancreatic carcinoma', 'missense')
    assert(mutation_dict['KRAS'] > 0)
