import re
from indra.statements import Phosphorylation, Agent, Evidence
from tests.integration import _IntegrationTest
from bioagents import Bioagent, BioagentException, make_evidence_html
from kqml import KQMLList, KQMLPerformative


def test_make_evidence_html1():
    # Full evidence
    ev1 = Evidence(source_api='trips', pmid='12345', text='Some evidence')
    # Has PMID but no text
    ev2 = Evidence(source_api='biopax', pmid='23456', text=None)
    # No PMID or text but has source id
    ev3 = Evidence(source_api='bel', pmid=None, text=None, source_id='bel_id')
    # No evidence other than the source API
    ev4 = Evidence(source_api='bel', pmid=None, text=None, source_id=None)
    stmt = Phosphorylation(Agent('A'), Agent('B'),
                            evidence=[ev1, ev2, ev3, ev4])
    ev_html = make_evidence_html([stmt], 'proof for a conclusion')
    assert len(re.findall('Found in', ev_html)) == 2
    assert len(re.findall('Found without', ev_html)) == 1
    print(ev_html)


class TestErrorHandling(_IntegrationTest):
    reason = 'Found it!'

    def __init__(self, *args):
        class FindMe(BioagentException):
            pass

        class TestAgent(Bioagent):
            name = 'test'
            tasks = ['TEST']

            def receive_request(self, msg, content):
                ret = None
                try:
                    ret = Bioagent.receive_request(self, msg, content)
                except FindMe:
                    reply_content = self.make_failure(TestErrorHandling.reason)
                if ret is None:
                    ret = self.reply_with_content(msg, reply_content)
                return ret

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
            "Exception caught too soon."
