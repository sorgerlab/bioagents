import unittest
from kappa_client import KappaRuntime, RuntimeError

class TestKappaClient(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestKappaClient, self).__init__(*args, **kwargs)
        self.endpoint = "http://localhost:8080"

    def test_version(self):
        runtime = KappaRuntime(self.endpoint)
        version = runtime.version()
        self.assertIsNotNone('version' in version)
        self.assertIsNotNone('build' in version)

    def test_parse(self):
        check = lambda parse : self.assertIsNotNone('observables' in parse)
        runtime = KappaRuntime(self.endpoint)
        parse = runtime.parse("")
        check(parse)
        parse = runtime.parse("%var: 'one' 1")
        check(parse)
        try :
            parse = runtime.parse("A(x!1),B(x!1) -> A(x),B(x) @ 0.01")
            assert(False)
            print "a"
        except RuntimeError as e:
            assert(e.errors == ['Error at line 1, characters 0-1: : "A" is not a declared agent.'])
        try :
            parse = runtime.parse("A(x)")
            assert(False)
        except RuntimeError as e:
            assert(e.errors == ['Error at line 1, characters 4-4: : Syntax error'])


    def start_parse(self):
        check = lambda parse : self.assertIsNotNone('observables' in parse)
        runtime = KappaRuntime(self.endpoint)
        parse = runtime.parse("")
        check(parse)
        print runtime.start("%var: 'one' 1")
        check(parse)
        try :
            parse = runtime.parse("A(x!1),B(x!1) -> A(x),B(x) @ 0.01")
            assert(False)
            print "a"
        except RuntimeError as e:
            assert(e.errors == ['Error at line 1, characters 0-1: : "A" is not a declared agent.'])
        try :
            parse = runtime.parse("A(x)")
            assert(False)
        except RuntimeError as e:
            assert(e.errors == ['Error at line 1, characters 4-4: : Syntax error'])

if __name__ == '__main__':
    unittest.main()
