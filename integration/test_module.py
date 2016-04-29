import sys
import argparse
import operator
import threading
import time

from jnius import autoclass, cast
from bioagents.trips.trips_module import TripsModule

# Declare KQML java classes
KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')

class Test_State():
    def __init__(self,request,expected):
        self.request = request
        self.expected = expected
        self.actual = None

    def get_request(self):
        return self.request

    def get_expected(self):
        return self.expected

    def set_actual(self,a):
        setattr(self, 'actual', a)
        print 'post:set_actual {0}'.format(self.get_actual())


    def get_actual(self):
        return self.actual

    def get_content(self):
        reply_content = KQMLList()        
        if self.get_actual():
            actual_string = self.get_actual().toString()
            expected_string = self.get_expected().toString()
            print 'get_content:actual_string {0}'.format(actual_string)
            print 'get_content:expected_string {0}'.format(expected_string)
            if expected_string in actual_string:
                return None
            else:
                reply_content.add(":request")
                reply_content.add(self.get_request())
                reply_content.add(":expected")
                reply_content.add(self.get_expected())                
                reply_content.add(":actual")
                reply_content.add(self.get_actual())
        else:
            reply_content.add(":request")
            reply_content.add(self.get_request())
            reply_content.add(":noresponse")
        return reply_content

class Unit_Test():
    '''
    This state of a collection of unit tests being
    rurn.
    '''
    def __init__(self):
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


    def reply(self,):
        reply_msg = KQMLPerformative('reply')
        reply_content = KQMLList()
        for t in self.tests:
            print 'reply {0}'.format(t)
            t_content = t.get_content()
            if t_content:
                reply_content.add(t_content.toString())
        reply_msg.setParameter(':content', cast(KQMLObject, reply_content))
        return reply_msg

class Handler():
    def __init__(self,reciever,unit_test):
        self.reciever = reciever
        self.unit_test = unit_test

    def start(self):
        if self.unit_test.current():
            self.test_state =  self.unit_test.current()
            request = self.test_state.get_request()
            request.add(':sender')
            request.add('Test')
            print 'runtest_time:test_state:{0}'.format(self.test_state)
            self.reciever.send_with_continuation(request,self)
            print 'runtest_time:request:{0}'.format(request.toString())
            self.unit_test.next()

    def receive(self,actual):
        print 'receive {0}'.format(self.test_state) 
        self.test_state.set_actual(actual)
        self.start()

def send_reply(self,msg,unit_test,):
    time.sleep(10)
    self.reply(msg, unit_test.reply())

class Test_Module(TripsModule):
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

        unit_test = Unit_Test()
        if task_str == 'ONT::PERFORM':
            for i in range(1,content_list.size()):
                test_wrapper = cast(KQMLList, content_list.get(i))
                if test_wrapper.get(0).toString().upper() == 'ONT::TEST':
                    request = cast(KQMLList, test_wrapper.get(1))
                    expected = test_wrapper.get(2)
                    unit_test.save_test(request,expected)
            self.runtest_time(msg,unit_test)
        else:
            self.error_reply(msg, 'unknown request task ' + task_str)
            return None

    def receive_reply(self, msg, content):
        '''
        Handle a "reply" message is received.
        '''
        print 'reply:msg:{0}'.format(msg)
        print 'reply:content:{0}'.format(content)
        return None

    def runtest_time(self, msg, unit_test):
        handler = Handler(self,unit_test)
        handler.start()
        t = threading.Thread(target=send_reply, args=(self,msg,unit_test,))
        t.start()

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
