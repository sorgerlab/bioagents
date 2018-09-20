import json

from kqml import KQMLList

from indra.statements import Agent, Activation, BoundCondition, stmts_to_json, \
    ActivityCondition, Phosphorylation

from bioagents.tests.util import get_request
from bioagents.bionlg.bionlg_module import BioNLG_Module
from bioagents.tests.integration import _IntegrationTest


kras = Agent('KRAS')
braf = Agent('BRAF')
map2k1 = Agent('MAP2K1')
mapk3 = Agent('MAPK3')
gtp = Agent('GTP')
active_braf = Agent('BRAF', activity=ActivityCondition('activity', True))
kras_bound = Agent("KRAS", bound_conditions=[BoundCondition(gtp, True)])


class _NlgTestBase(_IntegrationTest):
    message_funcs = ['statements']

    # Define these in the sub-classes with statements, and sentences that
    # correspond to those statements.
    statements = []
    sentences = []

    def __init__(self, *args, **kwargs):
        super(_NlgTestBase, self).__init__(BioNLG_Module)

    def create_statements(self):
        content = KQMLList('INDRA-TO-NL')
        content.sets('statements', json.dumps(stmts_to_json(self.statements)))
        return get_request(content), content

    def check_response_to_statements(self, output):
        assert output.head() == 'OK', output
        nl_list = output.get('nl')
        for i, sent in enumerate(nl_list):
            assert sent.string_value() == self.sentences[i],\
                "Expected %s, but got %s." % (sent, self.sentences[i])


class TestActiveFlag(_NlgTestBase):
    statements = [Activation(active_braf, map2k1)]
    sentences = ["Active BRAF activates MAP2K1"]


class TestBoundConditionAndResidues(_NlgTestBase):
    statements = [Phosphorylation(kras_bound, braf, position='373'),
                  Phosphorylation(braf, mapk3, residue='T', position='202')]
    sentences = ["KRAS bound to GTP phosphorylates BRAF",
                 "BRAF phosphorylates MAPK3 on T202"]


class TestTwoSimpleStatements(_NlgTestBase):
    statements = [Activation(kras, braf), Activation(kras, braf)]
    sentences = ["KRAS activates BRAF", "KRAS activates BRAF"]


class TestSimpleStatement(_NlgTestBase):
    statements = [Activation(kras, braf)]
    sentences = ["KRAS activates BRAF"]
