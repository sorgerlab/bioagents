import re
from datetime import datetime
from unittest import TestCase
from difflib import SequenceMatcher
import logging
from kqml.kqml_performative import KQMLPerformative
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('integration_tests')

try:
    from colorama.ansi import Back, Style, Fore
except ImportError:
    logger.warning('Will not be able to mark diffs with color.')

    # Create dummies
    class DummyColorer(object):
        def __getattribute__(self, *args, **kwargs):
            return ""
    Back = DummyColorer()
    Style = DummyColorer()
    Fore = DummyColorer()


def color_diff(expected, received):
    """Show in color the change in a string compaired to another."""
    sm = SequenceMatcher(None, received, expected)
    output = []
    for opcode, a0, a1, b0, b1 in sm.get_opcodes():
        if opcode == 'equal':
            output.append(sm.a[a0:a1])
        elif opcode == 'insert':
            output.append(Back.RED + sm.b[b0:b1] + Style.RESET_ALL)
        elif opcode == 'delete':
            output.append(Back.GREEN + sm.a[a0:a1] + Style.RESET_ALL)
        elif opcode == 'replace':
            output.append(Back.BLUE + sm.a[a0:a1] + Back.RESET +
                          Fore.BLUE + sm.b[b0:b1] + Style.RESET_ALL)
        else:
            raise Exception('unexpected opcode')
    return ''.join(output)


def define_in_child(s):
    return "Define %s in the child!" % s


class _IntegrationTest(TestCase):
    """An abstract class for running a series of requests to the bioagent.

    Much of the functionality of bioagents comes with their ability to
    respond to messages they receive. This is a template for tests that
    verify bioagents respond correctly to various messages.

    Class Attributes:
    ----------
    message_funcs: (list) A list of the message names to be sent. This can be
        used to set the order of execution, which is otherwise alphabetical.

    Methods:
    -------
    _get_messages: creates a generator that iterates over the message methods
        given by message_funcs, or else all methods with the `create_` prefix.
    run_test: runs the test.

    Special Methods in Children:
    ---------------------------
    create_<message_func_name>: These functions must take no inputs, and return
        a kqml msg and content to be input into the receive_request function of
        a bioagent.
    check_response_to_<message_func_name>: These functions contain asserts, and
        any other similar means of checking the result of the corresponding
        call to the bioagent, as per usual nosetest procedures.

    Example:
    -------
    As an example, a test sending two message to the bioagent, labeled prep and
    run, then checking the result of the run, may be written as follows:
    ```
    >> class TestFoo(_IntegrationTest):
    >>     message_funcs = ['prep', 'run']
    >>
    >>     def create_prep(self):
    >>         "Creates the kqml message (msg) and content (content) for prep."
    >>         ...
    >>         return msg, content
    >>
    >>     def create_run(self):
    >>         "Creates the kqml message and content for runing something."
    >>         ...
    >>         return msg, content
    >>
    >>     def check_response_to_run(self, output):
    >>         "Checks that the output from the run is valid."
    >>         ...
    ```
    This defines a test that sends a prep message, then a run message, and
    checks the result of the run message to determine the status of the test.
    Note that the prefixes are required for the methods to be found and used.
    Note also that unless `message_funcs` is defined, the messages will be sent
    in alphabetical order by default. Last of all, note that the `create_`
    methods must have no inputs (besides self), and the `check_response_to_`
    methods must have one input, which will be the output content of the
    `receive_request` call.

    Single requests may also be made without any difficulty or altering of the
    above paradigm. Note that message_funcs would not be needed in such cases.
    """
    message_funcs = []

    def __init__(self, bioagent, **kwargs):
        self.bioagent = bioagent(testing=True, **kwargs)
        self.this_test_log_start = None
        TestCase.__init__(self, 'run_test')
        return

    def __getattribute__(self, attr_name):
        "Ensure that all attributes are implemented."
        attr = TestCase.__getattribute__(self, attr_name)
        if attr is NotImplemented:
            raise NotImplementedError(define_in_child(attr_name))
        return attr

    def _get_method_dict(self, prefix=''):
        """Get a dict of methods with the given prefix string."""
        # We need to walk up the parental tree to get all relevant methods.
        # Note: the particular way the dicts are combined preserves parent
        # child priority, namely that a child method should always take
        # priority over like-named parent method.
        full_dict = {}
        current_class = self.__class__
        while issubclass(current_class, _IntegrationTest) and \
                current_class is not _IntegrationTest:
            full_dict = dict([
                (name, attr)
                for name, attr in current_class.__dict__.items()
                if not name.startswith('__')
                ] + list(full_dict.items()))
            current_class = current_class.__base__

        # Create the method dict.
        method_dict = {
            name[len(prefix):]: attr
            for name, attr in full_dict.items()
            if callable(attr) and name.startswith(prefix)
            }
        return method_dict

    def _get_messages(self):
        """Get a generator iterating over the methods to send messages.

        Yields:
        ------
        request_args: (tuple) arguements to be passed to `receive_request`.
        check_func: (callable) a function used to check the result of a
            request, or else None, if no such check is to be made.
        """
        send_dict = self._get_method_dict('create_')
        check_dict = self._get_method_dict('check_response_to_')
        if not self.message_funcs:
            msg_list = sorted(send_dict.keys())
        else:
            msg_list = self.message_funcs[:]
        assert len(msg_list), \
            "No messages found to test, likely error in def of test."
        for msg in msg_list:
            yield send_dict[msg](self), check_dict.get(msg)

    def get_output_log(self, start_line=0, end_line=None, get_full_log=False):
        """Get the messages sent by the bioagent."""
        buff = self.bioagent.out
        cur_pos = buff.tell()
        if get_full_log:
            buff.seek(0)
        elif self.this_test_log_start is not None:
            buff.seek(self.this_test_log_start)
        else:
            return []
        out_lines = re.findall('^(\(.*?\))$', buff.read().decode(),
                               re.MULTILINE | re.DOTALL)
        out_msgs = [KQMLPerformative.from_string(line) for line in out_lines]
        buff.seek(cur_pos)
        return out_msgs[start_line:end_line]

    def setUp(self):
        """Set the start of the logs"""
        self.this_test_log_start = self.bioagent.out.tell()
        logger.debug("Set log start to: %d" % self.this_test_log_start)

    def run_test(self):
        for request_args, check_resp in self._get_messages():
            start = datetime.now()
            self.bioagent.receive_request(*request_args)
            end = datetime.now()
            dt = end - start
            assert dt.total_seconds() < 40, \
                "Task took too long (%.2f seconds). BA would have timed out." \
                % dt.total_seconds()
            output = self.get_output_log()[-1].get('content')
            if check_resp is not None:
                check_resp(self, output)
        return

    def tearDown(self):
        """Unset the start of the log."""
        self.this_test_log_start = None


class _StringCompareTest(_IntegrationTest):
    """Integration test in which the expected result is a verbatim string."""
    def __init__(self, *args, **kwargs):
        super(_StringCompareTest, self).__init__(*args, **kwargs)
        self.expected = NotImplemented

    def create_message(self):
        raise NotImplementedError(define_in_child("the message constructor"))

    def check_response_to_message(self, output):
        output_str = output.to_string()
        assert output_str == self.expected, (
            'Did not get the expected output string:\n'
            + 'Expected: %s\n' % self.expected
            + 'Received: %s\n' % output.to_string()
            + 'Diff: %s\n' % color_diff(self.expected, output.to_string())
            )


class _FailureTest(_IntegrationTest):
    """Integration test in which the expected result is a failure."""
    def __init__(self, *args, **kwargs):
        super(_FailureTest, self).__init__(*args, **kwargs)
        self.expected_reason = NotImplemented

    def check_response_to_message(self, output):
        assert output.head() == 'FAILURE', 'Head is not FAILURE'
        reason = output.gets('reason')
        assert reason == self.expected_reason, \
            'Reason mismatch: %s instead of %s' % \
            (reason, self.expected_reason)
