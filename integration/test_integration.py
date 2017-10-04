import sys
import time
import logging
import re
from subprocess import Popen
from time import sleep
from os import path, listdir, environ, remove
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

from difflib import SequenceMatcher
try:
    from colorama import Back, Style, Fore
except ImportError:
    raise Warning("Will not be able to mark diffs with color.")
    # Create dummies
    class DummyColorer(object):
        def __getattribute__(self, *args, **kwargs):
            return ""
    class Back(DummyColorer):
        pass
    class Style(DummyColorer):
        pass
    class Fore(DummyColorer):
        pass

BIOAGENT_DICT = {
    'tra': TRA_Module,
    'qca': QCA_Module,
    'mra': MRA_Module,
    'bionlg': BioNLG_Module,
    'biosense': BioSense_Module,
    'dtda': DTDA_Module,
    'mea': MEA_Module,
    'kappa': Kappa_Module
    }

class TestError(Exception):
    pass

def run_bioagent(stop_event, ba_name, **kwargs):
    BA_inst = BIOAGENT_DICT[ba_name](name=ba_name, **kwargs)
    while not stop_event.is_set():
        sleep(1)
    BA_inst.exit()
    return


class Bioagent_Thread(Thread):
    """A stoppable thread designed for use with the bioagent modules."""
    def __init__(self, ba_name, **kwargs):
        ba_kwargs = kwargs.pop('kwargs', {})
        self._stop_event = Event()
        super(Bioagent_Thread, self).__init__(
            target = run_bioagent,
            args = (self._stop_event, ba_name),
            kwargs=ba_kwargs,
            **kwargs)
        return
    
    def stop(self):
        self._stop_event.set()

    def stopping(self):
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
        logger.info('Collected %s test messages from %s' % \
              (self.total_tests, test_file))
        # Send off the first test
        sm = self.sent.pop()
        self.send(self.get_perf(self.msg_counter, sm))
        self.msg_counter += 1

    def color_diff(self, str1, str2):
        """Show in color the change in a string compaired to another."""
        sm = SequenceMatcher(None, str2, str1)
        output= []
        for opcode, a0, a1, b0, b1 in sm.get_opcodes():
            if opcode == 'equal':
                output.append(sm.a[a0:a1])
            elif opcode == 'insert':
                output.append(Back.RED + sm.b[b0:b1] + Style.RESET_ALL)
            elif opcode == 'delete':
                output.append(Back.GREEN + sm.a[a0:a1] + Style.RESET_ALL)
            elif opcode == 'replace':
                output.append(Back.CYAN + sm.a[a0:a1] + Back.RESET + 
                              Fore.CYAN + sm.b[b0:b1] + Style.RESET_ALL)
            else:
                raise KappaRuntimeError, "unexpected opcode"
        return ''.join(output)


    def receive_reply(self, msg, content):
        """Handle a "reply" message being received."""
        expected_content = self.expected.pop().strip()
        actual_content = content.__repr__().strip()
        colored_content = self.color_diff(expected_content, actual_content)
        logger.info('expected:  %s' % expected_content)
        logger.info('actual:    %s' % actual_content)
        logger.info('colordiff: %s' % colored_content)
        if expected_content == actual_content:
            self.passed_tests += 1
            logger.info('PASS')
        else:
            logger.info('FAIL')
        logger.info('---')

        if not self.sent.is_empty():
            sm = self.sent.pop()
            self.send(self.get_perf(self.msg_counter, sm))
            self.msg_counter += 1
        if self.expected.is_empty():
            logger.info('%d PASSED / %d FAILED' % \
                        (self.passed_tests,
                         self.total_tests - self.passed_tests))
            self.dispatcher.shutdown()
            return


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
    """The master testing object that will manage the test module and inputs"""
    def __init__(self, inputs):
        self._cleaning = True
        clean_opts = {'--nocleanup', '-nc'}.intersection(inputs)
        if len(clean_opts) > 0:
            self._cleaning = False
            [inputs.remove(opt) for opt in clean_opts]
        self._facilitator = self._find_facilitator()

        logger.info("Looking up the available tests.")
        self._loc = path.dirname(path.abspath(__file__))
        patt = re.compile(r'(test_(\w+?)\.in)')
        self._init_state = listdir(self._loc)
        matches = map(patt.match, self._init_state)
        self._input_files = {}
        for m in filter(lambda x: x is not None, matches):
            self._input_files[m.groups()[1]] = m.groups()[0]

        logger.info("Selecting tests to run.")
        self._test_list = []
        if 'all' in inputs:
            self._test_list = self._input_files.keys()
        else:
            for inp in inputs:
                if inp in self._input_files.keys():
                    self._test_list.append(inp)
                else:
                    raise InputError('Unrecognized bioagent test: %s' % inp)

        self._trips_handle = None
        self._bioagent_handle = None
        return

    def _find_facilitator(self):
        trips_base = environ.get('TRIPS_BASE')
        if not trips_base:
            home = path.expanduser('~')
            trips_base = path.join(home, 'Workspace', 'cwc-integ',
                                   'trips', 'bob')
        facilitator = path.join(trips_base, 'bin', 'Facilitator')
        if not path.exists(facilitator):
            logger.error('Could not find TRIPS Facilitator at %s' %
                         facilitator)
            sys.exit(1)
        return facilitator

    def _trips_is_running(self):
        """Check if the trips process is running"""
        if self._trips_handle is None:
            return False
        if self._trips_handle.poll() is None:
            return True
        return False

    def _start_trips(self):
        """Begin the trips process"""
        logger.info("Starting trips.")
        if not self._trips_is_running():
            with open('init.trips', 'rb') as inp:
                self._trips_handle = Popen([self._facilitator], stdin=inp)
            if not self._trips_is_running():
                #TODO: Give move feedback by getting stdout from trips.
                raise TestError('Trips facilitator failed to start.')
            time.sleep(5)
        return

    def _run_bioagent_test(self, ba_name):
        """Run a the test for a single bioagent"""
        logger.info('=' * 30)
        logger.info("RUNNING TEST ON: %s." % ba_name)
        try:
            self._start_bioagent(ba_name)
            # Sleep here to make sure Bioagent is started before test
            sleep(5)
            tm = Test_Module(self._input_files[ba_name],
                             name=('Test_' + ba_name))
            tm.start()
            self._stop_bioagent()
            # Sleep here to make sure Bioagent is stopped before next test
            sleep(5)
        except Exception as e:
            logger.error(e)
            logger.error('Encountered exception while running %s test.' %
                         ba_name)
        return

    def _start_bioagent(self, ba_name):
        """Start up the process for a bioagent"""
        logger.info("Starting bioagent thread for: %s." % ba_name)
        if self._bioagent_handle is not None:
            raise TestError('Attempted to start a bioagent with another'
                            ' already running.')

        self._bioagent_handle = Bioagent_Thread(ba_name)
        self._bioagent_handle.start()
        if not self._bioagent_handle.is_alive():
            raise TestError('Bioagent thread died unexpectedly.')

        return

    def _stop_bioagent(self):
        """Stop the current bioagent"""
        logger.info("Stopping bioagent thread.")
        if self._bioagent_handle is not None:
            self._bioagent_handle.stop()
            self._bioagent_handle.join(timeout=5)
            if self._bioagent_handle.stopped() and not self._bioagent_handle.is_alive():
                self._bioagent_handle = None
            else:
                raise TestError('Could not stop bioagent thread.')
        return

    def _stop_trips(self):
        """Stop trips facilitator"""
        logger.info("Stopping trips facilitator.")
        if self._trips_is_running():
            self._trips_handle.kill()
            sleep(3)
            if self._trips_is_running():
                raise TestError('Could not kill trips.')
            self._trips_handle = None
        return

    def run_tests(self):
        """Run all the tests"""
        logger.info("Running tests.")
        self._start_trips()
        try:
            for ba_name in self._test_list:
                self._run_bioagent_test(ba_name)
        finally:
            self._stop_trips()
            if self._cleaning:
                self._cleanup()
        return

    def _cleanup(self):
        """Remove all new files spawned during test."""
        for name in listdir(self._loc):
            name_path = path.join(self._loc, name)
            if name not in self._init_state and path.isfile(name_path):
                remove(name_path)

if __name__ == "__main__":
    try:
        tester = Test_Harness(sys.argv[1:])
        tester.run_tests()
    except:
        raise
