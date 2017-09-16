from unittest import TestCase
from difflib import SequenceMatcher
from io import BytesIO
from kqml.kqml_performative import KQMLPerformative

import logging
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('integration_tests')

try:
    from colorama.ansi import Back, Style, Fore
except:
    logger.warning('Will not be able to mark diffs with color.')

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
            output.append(Back.CYAN + sm.a[a0:a1] + Back.RESET +
                          Fore.CYAN + sm.b[b0:b1] + Style.RESET_ALL)
        else:
            raise RuntimeError('unexpected opcode')
    return ''.join(output)


class ParentIntegChecks:
    class IntegCheckParent(TestCase):
        """An abstract object for creating integration tests of bioagents.

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
        nie_fmt = "Define %s in the child!"

        def __init__(self, Bioagent):
            self.output = None  # BytesIO()
            self.bioagent = Bioagent(testing=True)  # out = self.output)
            TestCase.__init__(self, 'run_test')
            return

        def __getattribute__(self, attr_name):
            "Ensure that all attributes are implemented."
            attr = TestCase.__getattribute__(self, attr_name)
            if attr is NotImplemented:
                raise NotImplementedError(self.nie_fmt % attr_name)
            return attr

        def get_message(self):
            "(Stub) Get the message to be sent to the Bioagent."
            raise NotImplementedError(self.nie_fmt % "the message constructor")

        def is_correct_response(self):
            "Check that the response is correct. Must be defined in child."
            raise NotImplementedError(self.nie_fmt % "the response criteria")

        def give_feedback(self):
            "Create an informative string to give some feedback."
            raise NotImplementedError(self.nie_fmt % "feedback")

        def run_test(self):
            msg, content = self.get_message()
            self.output = self.bioagent.receive_request(msg, content)
            # self.bioagent.dispatcher.dispatch_message(msg)
            assert self.is_correct_response(), self.give_feedback()


class FirstGenIntegChecks:
    class ComparativeIntegCheck(ParentIntegChecks.IntegCheckParent):
        def __init__(self, *args, **kwargs):
            ParentIntegChecks.IntegCheckParent.__init__(self, *args, **kwargs)
            self.expected = NotImplemented
            return

        def give_feedback(self):
            """Give feedback comparing the expected to the result."""
            ret_fmt = 'Did not get the expected output string:\n'
            ret_fmt += 'Expected: %s\nReceived: %s\nDiff: %s\n'
            if self.output is None:
                res = 'None'
            elif isinstance(self.output, tuple) and len(self.output) > 1:
                if isinstance(self.output[1], KQMLPerformative):
                    res = self.output[1].to_string()
                else:
                    res = str(self.output[1])
            else:
                return "UNHANDLED RESULT TYPE"

            return ret_fmt % (self.expected, res,
                              color_diff(self.expected, res))
