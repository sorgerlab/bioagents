import sys
import time
import argparse
import operator
import threading

from kqml import KQMLModule, KQMLPerformative, KQMLList


class TestModule(KQMLModule):
    """The Test module is a TRIPS module built to run unit tests.

    Its role is to receive and decode messages and send responses to
    other agents in the system.
    """
    def __init__(self, argv, file_in):
        # Call the constructor of TripsModule
        super(TestModule, self).__init__(argv)
        self.expected = FIFO()
        self.sent = FIFO()
        self.test_file = file_in
        self.msg_counter = 1
        # Send ready message
        self.ready()
        self.initialize_tests(self.test_file)
        return None

    def get_perf(self, msg_id, msg_txt):
        msg_txt = msg_txt.replace('\\n', '\n')
        perf  = KQMLPerformative.from_string(
            '(request :reply-with IO-%d :content %s)' % (msg_id, msg_txt))
        return perf

    def initialize_tests(self, test_file):
        fh = open(test_file, 'rt')
        messages = fh.readlines()
        send_msg = messages[0::2]
        expect_msg = messages[1::2]
        for sm, em in zip(send_msg, expect_msg):
            # TODO: allow non-request messages?
            self.sent.push(sm)
            self.expected.push(em)
        print('Collected %s test messages from %s' % \
              (len(self.sent.lst), test_file))
        # Send off the first test
        sm = self.sent.pop()
        self.send(self.get_perf(self.msg_counter, sm))
        self.msg_counter += 1

    def receive_reply(self, msg, content):
        """Handle a "reply" message being received."""
        expected_content = self.expected.pop().strip()
        actual_content = content.__repr__().strip()
        print('expected: %s' % expected_content)
        print('actual:   %s' % actual_content)
        print('---')
        assert(expected_content == actual_content)
        if not self.sent.is_empty():
            sm = self.sent.pop()
            self.send(self.get_perf(self.msg_counter, sm))
            self.msg_counter += 1
        if self.expected.is_empty():
            sys.exit(0)

class FIFO(object):
    def __init__(self, lst=None):
        if lst is None:
            self.lst = []
        else:
            self.lst = lst

    def pop(self):
        return self.lst.pop()

    def push(self, e):
        self.lst = [e] + self.lst

    def is_empty(self):
        if not self.lst:
            return True
        return False

if __name__ == "__main__":
    m = TestModule(['-name', 'Test'] + sys.argv[2:], sys.argv[1])
    m.start()
