from tests.integration import _IntegrationTest
from bioagents import Bioagent, BioagentException
from kqml import KQMLList, KQMLPerformative


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
