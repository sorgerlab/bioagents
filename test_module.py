import sys
import argparse
import operator
import sched, time

from jnius import autoclass, cast
from TripsModule import trips_module

# Declare KQML java classes
KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')

class Test_State():
    def __init__(self,request,expected):
        self.request = request
        self.expected = expected
        self.actual = None
    def get_expected():
        return expected

    def get_actual():
        return actual

    def set_actual(self,actual):
        self.actual = actual

    def get_actual(self):
        return self.actual

class Unit_Test():
    '''
    This state of a collection of unit tests being
    rurn.
    '''
    def __init__(self,msg):
        self.msg = msg
        self.tests = []
        self.state = []
    '''
    This class returns the current test being
    
    '''
    def save_test(self,request,expected):
        self.state.append(Test_State(request,expected))
        self.tests =  self.state[:]

    def current(self):
        if self.state:
            return self.state[0]
        else:
            return None
    
    def next(self):
        return self.state.pop(0)

class Handler():
    def __init__(self,test_state):
        self.test_state = test_state
        
    def receive(self,actual):
        self.test_state.set_actual(actual)

class Test_Module(trips_module.TripsModule):
    '''
    The Test module is a TRIPS module built to run unit test. It will
    ts role is to receive and decode messages and send responses from
    and to other agents in the system.
    '''
    def __init__(self, argv):
        # Call the constructor of TripsModule
        super(Test_Module, self).__init__(argv)
        self.tasks = {'ONT::PERFORM': ['ONT::TEST']}


    def init(self):
        '''
        Initialize TRIPS module
        '''
        super(Test_Module, self).init()
        # Send subscribe messages
        for task, subtasks in self.tasks.iteritems():
            for subtask in subtasks:
                msg_txt = '(subscribe :content (request &key :content ' +\
                    '(%s &key :content (%s . *))))' % (task, subtask)
                self.send(KQMLPerformative.fromString(msg_txt))
        # Send ready message
        self.ready()
        return None
    
    def receive_request(self, msg, content):
        '''
        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        "tell" message is then sent back.
        '''
        content_list = cast(KQMLList, content)
        task_str = content_list.get(0).toString().upper()

        self.unit_test = Unit_Test(msg)
        if task_str == 'ONT::PERFORM':
            for i in range(1,content_list.size()):
                test_wrapper = cast(KQMLList, content_list.get(i))
                if test_wrapper.get(0).toString().upper() == 'ONT::TEST':
                    request = cast(KQMLList, test_wrapper.get(1))
                    expected = test_wrapper.get(2)
                    self.unit_test.save_test(request,expected)
            self.runtest_time()
        else:
            self.error_reply(msg, 'unknown request task ' + task_str)
            return None

    def receive_reply(self, msg, content):
        '''
        Handle a "reply" message is received.
        '''
        print msg
        print content
        return None

    def runtest_time(self):
        while self.unit_test.current():
            test_state =  self.unit_test.current()
            request.add(':sender')
            request.add('Test')
            self.send_with_continuation(request, Handler(self.unit_test))
            self.expected = expected
            print request.toString()
            time.sleep(5)
            self.unit_test.next()
        print "done runtest_time"
        
        reply_msg = KQMLPerformative('reply')
        self.reply(self.unit_test.get_msg(), reply_msg)

    def respond_test(self):
        '''
        Response content to version message
        '''
        reply_content = KQMLList()
        version_response = KQMLList.fromString( '' +\
            '(ONT::TELL :content ' +\
            ')')

        reply_content.add(KQMLList(version_response))
        return reply_content

if __name__ == "__main__":
    dm = Test_Module(['-name', 'Test'] + sys.argv[1:])
    dm.run()
