from io import BytesIO
from unittest import TestCase
from difflib import SequenceMatcher
from kqml.kqml_performative import KQMLPerformative
import logging
from docutils.parsers.rst.states import InterpretedRoleNotImplementedError
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


class _IntegrationTest_deprecated(TestCase):
    """An abstract class for creating integration tests of bioagents.

    Much of the functionality of bioagents comes with their ability to
    respond to messages they receive. This is a template for tests that
    verify bioagents respond correctly to various messages.

    NOTE: The stubs must be overwritten in the child.

    Methods:
    -------
    get_message: (stub) Generate the message that will be sent to the
        bioagent. Returns some form of KQML object that can be sent as a
        message, e.g. a KQMLPerformative.

    is_correct_response: (stub) Determine if the response is correct.
        Returns a bool: True if the response is correct, else False (as per
        natural interpretation).

    give_feedback: (stub) Generate feedback for a test failure.

    run_test: Actually run the test. This makes calls to the stubs.
    """

    def __init__(self, bioagent, **kwargs):
        self.output = None  # BytesIO()
        self.bioagent = bioagent(testing=True, **kwargs)  # out = self.output)
        TestCase.__init__(self, 'run_test')

    def __getattribute__(self, attr_name):
        "Ensure that all attributes are implemented."
        attr = TestCase.__getattribute__(self, attr_name)
        if attr is NotImplemented:
            raise NotImplementedError(define_in_child(attr_name))
        return attr

    def get_message(self):
        "Get the message to be sent to the Bioagent."
        raise NotImplementedError(define_in_child('the message constructor'))

    def is_correct_response(self):
        "Check that the response is correct. Must be defined in child."
        raise NotImplementedError(define_in_child('the response criteria'))

    def give_feedback(self):
        "Create an informative string to give some feedback."
        raise NotImplementedError(define_in_child('the feedback'))

    def run_test(self):
        msg, content = self.get_message()
        _, self.output = self.bioagent.receive_request(msg, content)
        assert self.is_correct_response(), self.give_feedback()


class _IntegrationTest(TestCase):
    """An abstract class for running a series of requests to the bioagent.

    As an example, such a test may be written as follows:

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
    Note that the `send_` and `check_` prefixes are required to for the mehtods
    to be found and used. Note also that unless `message_funcs` is defined, the
    messages will be sent in alphabetical order by default. Last of all, note
    that the `send_` methods must have no inputs (besides self), and the
    `check_` methods must have one input, which will be the output content of
    `receive_request` call.
    
    Single requests may also be made without any difficulty or altering of the
    above paradigm. Note that message_funcs would not be needed in such cases.
    
    Attributes:
    ----------
    message_funcs: (list) A list of the message names to be sent. This can be
        used to set the order of execution, which is otherwise alphabetical.
    
    Methods:
    -------
    _get_messages: creates a generator that iterates over the message methods 
        given by message_funcs, or else all methods with the `send_` prefix.
    run_test: runs the test.

    Special Methods in Children:
    ---------------------------
    create_<message_func_name>: These functions must take no inputs, and return
        a kqml msg and content to be input into the receive_request function of
        a bioagent.
    check_response_to_<message_func_name>: These functions contain asserts, and
        any other similar means of checking the result of the corresponding call
        to the bioagent, as per usual nosetest procedures. 
    """
    message_funcs = []

    def __init__(self, bioagent, **kwargs):
        self.output = None  # BytesIO()
        self.bioagent = bioagent(testing=True, **kwargs)  # out = self.output)
        TestCase.__init__(self, 'run_test')

    def __getattribute__(self, attr_name):
        "Ensure that all attributes are implemented."
        attr = TestCase.__getattribute__(self, attr_name)
        if attr is NotImplemented:
            raise NotImplementedError(define_in_child(attr_name))
        return attr

    def _get_method_dict(self, prefix=''):
        """Get a dict of methods with the given prefix string."""
        return {
            name.lstrip(prefix): attr 
            for name, attr in self.__dict__.iteritems() 
            if callable(attr) and name.startswith(prefix)
            }

    def _get_messages(self):
        """Get a generator iterating over the methods to send messages.
        
        Yields:
        ------
        request_args: (tuple) arguements to be passed to `receive_request`.
        check_func: (callable) a function used to check the result of a request,
            or else None, if no such check is to be made.
        """
        send_dict = self._get_method_dict('create_')
        check_dict = self._get_method_dict('check_response_to_')
        if not self.message_funcs:
            msg_list = send_dict.iterkeys()
        else:
            msg_list = self.message_funcs[:]
        for msg in msg_list:
            yield send_dict[msg](), check_dict.get(msg)

    def run_test(self):
        """Run the test."""
        for request_args, check_resp in self._get_messages():
            _, output = self.bioagent.receive_request(*request_args)
            if check_resp is not None:
                check_resp(output)


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
