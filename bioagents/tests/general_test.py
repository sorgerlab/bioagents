from indra.statements import Agent, Phosphorylation, ModCondition
from bioagents.tests.integration import _IntegrationTest
from bioagents import Bioagent, BioagentException
from kqml import KQMLList, KQMLPerformative


class TestErrorHandling(_IntegrationTest):
    reason = 'FOUND-IT'

    def __init__(self, *args):
        class FindMe(BioagentException):
            pass

        class TestAgent(Bioagent):
            name = 'test'
            tasks = ['TEST']

            def receive_request(self, msg, content):
                try:
                    Bioagent.receive_request(self, msg, content)
                    return
                except FindMe:
                    reply_content = self.make_failure(TestErrorHandling.reason)
                    self.reply_with_content(msg, reply_content)
                    return

            def respond_test(self, content):
                raise FindMe()

        super(TestErrorHandling, self).__init__(TestAgent)

    def create_message(self):
        content = KQMLList('TEST')
        content.sets('description', '')
        msg = KQMLPerformative('REQUEST')
        msg.set('content', content)
        return msg, content

    def check_response_to_message(self, output):
        head = output.head()
        assert head == "FAILURE",\
            "Got wrong output head: %s instead of FAILURE." % head
        assert output.get('reason') == self.reason,\
            ("Exception caught too soon (wrong reason: %s)."
             % output.get('reason'))


def test_cljson():
    ag = Agent('BRAF',
               mods=[ModCondition('phosphorylation', 'T', '396', False)],
               db_refs={'TEXT': 'Braf', 'HGNC': '123'})
    cj = Bioagent.make_cljson(ag)
    ag2 = Bioagent.get_agent(cj)
    assert ag.equals(ag2)
