import sys
import time
import logging
import re
from subprocess import Popen, PIPE
from time import sleep
from os import path, listdir
from docutils.io import InputError
from threading import Thread, Event
from bioagents.tra.tra_module import TRA_Module
from bioagents.qca.qca_module import QCA_Module
from bioagents.mra.mra_module import MRA_Module
from bioagents.bionlg.bionlg_module import BioNLG_Module
from bioagents.biosense.biosense_module import BioSense_Module
from bioagents.dtda.dtda_module import DTDA_Module
from bioagents.mea.mea_module import MEA_Module
from bioagents.kappa.kappa_module import Kappa_Module
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('Test')

from kqml import KQMLModule, KQMLPerformative, KQMLList

BIOAGENT_DICT={
    'tra':TRA_Module,
    'qca':QCA_Module,
    'mra':MRA_Module,
    'bionlg':BioNLG_Module,
    'biosense':BioSense_Module,
    'dtda':DTDA_Module,
    'mea':MEA_Module,
    'kappa':Kappa_Module
    }

class TestError(Exception):
    pass

class Bioagent_Thread(Thread):
    '''A stoppable thread designed for use with the bioagent modules.'''
    def __init__(self, ba_name, **kwargs):
        ba_kwargs = kwargs.pop('kwargs', {})
        ba_kwargs.update(name = ba_name)
        super(Bioagent_Thread, self).__init__(
            target = BIOAGENT_DICT[ba_name], 
            kwargs=ba_kwargs,
            **kwargs)
        self._stop_event = Event()
        return
    
    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()


class Test_Module(KQMLModule):
    """The Test module is a TRIPS module built to run unit tests.

    Its role is to receive and decode messages and send responses to
    other agents in the system.
    """
    def __init__(self, file_in, **kwargs):
        # Call the constructor of TripsModule
        super(Test_Module, self).__init__(**kwargs)
        self.expected = FIFO()
        self.sent = FIFO()
        self.total_tests = 0
        self.passed_tests = 0
        self.msg_counter = 1
        # Send ready message
        self.ready()
        self.initialize_tests(file_in)
        return None

    def get_perf(self, msg_id, msg_txt):
        msg_txt = msg_txt.replace('\\n', '\n')
        perf  = KQMLPerformative.from_string(
            '(request :reply-with IO-%d :content %s)' % (msg_id, msg_txt))
        return perf

    def initialize_tests(self, test_file):
        with open(test_file, 'rt') as fh:
            messages = fh.readlines()
        send_msg = messages[0::2]
        expect_msg = messages[1::2]
        for sm, em in zip(send_msg, expect_msg):
            # TODO: allow non-request messages?
            self.sent.push(sm)
            self.expected.push(em)
        self.total_tests = len(self.sent.lst)
        print('Collected %s test messages from %s' % \
              (self.total_tests, test_file))
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
        if expected_content == actual_content:
            self.passed_tests += 1
            print('PASS')
        else:
            print('FAIL')
        print('---')

        if not self.sent.is_empty():
            sm = self.sent.pop()
            self.send(self.get_perf(self.msg_counter, sm))
            self.msg_counter += 1
        if self.expected.is_empty():
            print('%d PASSED / %d FAILED' % \
                  (self.passed_tests, self.total_tests-self.passed_tests))
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


class Test_Harness(object):
    '''The master testing object that will manage the test module and inputs'''
    facilitator = '/home/patrick/Workspace/cwc-integ/trips/bob/bin/Facilitator'
    def __init__(self, inputs):
        print("Looking up the available tests.")
        loc = path.dirname(path.abspath(__file__))
        patt = re.compile(r'(test_(\w+?)\.in)')
        matches=filter(lambda x: x is not None, map(patt.match, listdir(loc)))
        self.input_files = {}
        for m in matches:
            self.input_files[m.groups()[1]] = m.groups()[0]

        print("Selecting tests to run.")
        self.run_with = []
        if 'all' in inputs:
            self.run_with = self.input_files.keys()
        else:
            for inp in inputs:
                if inp in self.input_files.keys():
                    self.run_with.append(inp)
                else:
                    raise InputError('Unrecoqnized bioagent test: %s' % inp)
        
        self.trips_handle = None
        self.bioagent_handle = None
        return
    
    def trips_is_running(self):
        '''Check if the trips process is running'''
        if self.trips_handle is None:
            return False
        if self.trips_handle.poll() is None:
            return True
        return False
    
    def start_trips(self):
        '''Begin the trips process'''
        print("Starting trips.")
        if not self.trips_is_running():
            with open('init.trips', 'rb') as inp:
                self.trips_handle = Popen([self.facilitator], stdin=inp)
            if not self.trips_is_running():
                #TODO: Give move feedback by getting stdout from trips.
                raise TestError('Trips facilitator failed to start.')
            time.sleep(5)
        return
    
    def run_bioagent_test(self, ba_name):
        '''Run a the test for a single bioagent'''
        print("Running test on: %s." % ba_name)
        self.start_bioagent(ba_name)
        tm = Test_Module(self.input_files[ba_name], name='Test_' + ba_name)
        tm.start()
        self.stop_bioagent()
        return
    
    def start_bioagent(self, ba_name):
        '''Start up the process for a bioagent'''
        print("Starting bioagent thread for: %s." % ba_name)
        if self.bioagent_handle is not None:
            raise TestError('Attempted to start a bioagent with another already running.')
        
        self.bioagent_handle = Bioagent_Thread(ba_name)
        self.bioagent_handle.start()
        if not self.bioagent_handle.is_alive():
            raise TestError('Bioagent thread died unexpectedly.')
        
        return
    
    def stop_bioagent(self):
        '''Stop the current bioagent'''
        print("Stopping bioagent thread.")
        if self.bioagent_handle is not None:
            self.bioagent_handle.stop()
            self.bioagent_handle.join(timeout=5)
            if self.bioagent_handle.stopped():
                self.bioagent_handle = None
            else:
                raise TestError('Could not stop bioagent thread.')
        return
        
        
    def stop_trips(self):
        '''Stop trips facilitator'''
        print("Stopping trips facilitator.")
        if self.trips_is_running():
            self.trips_handle.kill()
            self.trips_handle.wait(timeout=5)
            if self.trips_is_running():
                raise TestError('Could not kill trips.')
            self.trips_handle = None
        return
    
    def run_tests(self):
        '''Run all the tests'''
        print("Running tests.")
        self.start_trips()
        for ba_name in self.run_with:
            self.run_bioagent_test(ba_name)
        self.stop_trips()
        return


if __name__ == "__main__":
    tester = Test_Harness(sys.argv[1:])
    tester.run_tests()
