import sys
import argparse
import operator
import threading
import time

from jnius import autoclass, cast
from TripsModule.trips_module import TripsModule

# Declare KQML java classes
KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')

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

class TestModule(TripsModule):
    '''
    The Test module is a TRIPS module built to run unit test. It will
    ts role is to receive and decode messages and send responses from
    and to other agents in the system.
    '''
    def __init__(self, argv):
        # Call the constructor of TripsModule
        super(TestModule, self).__init__(argv)
        self.expected = FIFO()
        self.sent = FIFO()
        # TODO:make this an input argument
        self.test_file = 'integration/test.in'

    def init(self):
        '''
        Initialize TRIPS module
        '''
        super(TestModule, self).init()
        # Send ready message
        self.ready()
        self.run_tests(self.test_file)
        return None

    def run_tests(self, test_file):
        fh = open(test_file, 'rt')
        messages = fh.readlines()
        send_msg = messages[0::2]
        expect_msg = messages[1::2]
        msg_id = 1
        for sm, em in zip(send_msg, expect_msg):
            msg_id_str = 'IO-%d' % msg_id
            # TODO: allow non-request messages?
            perf  = KQMLPerformative.fromString(
                '(request :reply-with %s :content %s)' % (msg_id_str, sm))
            self.sent.push(sm)
            self.expected.push(em)
            self.send(perf)
            msg_id += 1

    def receive_reply(self, msg, content):
        '''
        Handle a "reply" message is received.
        '''
        sent = self.sent.pop().strip()
        expected_content = self.expected.pop().strip()
        actual_content = content.toString().strip()
        print 'sent:     ', sent
        print 'expected: ', expected_content
        print 'actual:   ', actual_content
        print '---'
        assert(expected_content == actual_content)
        if self.expected.is_empty():
            sys.exit(0)

if __name__ == "__main__":
    dm = TestModule(['-name', 'Test'] + sys.argv[1:])
    dm.run()
