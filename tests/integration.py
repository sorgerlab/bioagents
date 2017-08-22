from unittest import TestCase
from difflib import SequenceMatcher
from io import BytesIO
try:
    from colorama.ansi import Back, Style, Fore
except:
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

def color_diff(expected, received):
    """Show in color the change in a string compaired to another."""
    sm = SequenceMatcher(None, received, expected)
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
            raise RuntimeError, "unexpected opcode"
    return ''.join(output)

class ParentIntegChecks:
    class IntegCheckParent(TestCase):
        """An abstract object for creating integration tests of bioagents.
        
        Much of the functionality of bioagents comes with their ability to respond
        to messages they receive. This is a template for tests that verify
        bioagents respond correctly to various messages.
        
        NOTE: The stubs must be overwritten in the child.
        
        Methods:
        -------
        get_message: (stub) Generate the message that will be sent to the bioagent.
            Returns some form of KQML object that can be sent as a message, e.g. a
            KQMLPerformative.
        
        is_correct_response: (stub) Determine if the response is correct. Returns a
            bool: True if the response is correct, else False (as per natural
            interpretation).
        
        give_feedback: (stub) Generate feedback for a test failure.
        
        run_test: Actually run the test. This makes calls to the stubs.
        """
        def __init__(self, Bioagent, name):
            self.output = BytesIO()
            self.bioagent = Bioagent(name=name, 
                                     testing=True, 
                                     out = self.output)
            TestCase.__init__(self, 'run_test')
            return
        
        def get_message(self):
            "Get the message to be sent to the Bioagent. Must be defined in child."
            raise NotImplementedError('Define the message in the child.')
        
        def is_correct_response(self):
            "Check that the response is correct. Must be defined in child."
            raise NotImplementedError("Define the response critera in the child.")
        
        def run_test(self):
            msg = self.get_message()
            self.bioagent.dispatcher.dispatch_message(msg)
            assert self.is_correct_response(), self.give_feedback()
        
        def give_feedback(self):
            "Create an informative string to give some feedback."
            raise NotImplementedError("Define feedback in child")

class FirstGenIntegChecks:
    class ComparativeIntegCheck(ParentIntegChecks.IntegCheckParent):
        def __init__(self, *args, **kwargs):
            ParentIntegChecks.IntegCheckParent.__init__(self, *args, **kwargs)
            self.expected = NotImplemented
            return
        
        def give_feedback(self):
            "Give feedback comparing the expected to the result."
            if self.expected is NotImplemented:
                raise NotImplementedError("Specify expectation in child.")
            
            ret_fmt = 'Did not get the expected output string:\n'
            ret_fmt += 'Excpected: %s\nReceived: %s\nDiff: %s\n'
            res = self.output.getvalue()
            return ret_fmt % (self.expected, res, color_diff(self.expected, res))

            
            