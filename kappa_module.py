import sys
import argparse
import operator
from jnius import autoclass, cast
from TripsModule import trips_module
from kappa_client import KappaRuntime, RuntimeError

# Declare KQML java classes
KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')

class Kappa_Module(trips_module.TripsModule):
    '''
    The DTDA module is a TRIPS module built around the Kappa client. Its role
    is to receive and decode messages and send responses from and to other
    agents in the system.
    '''
    def __init__(self, argv):
        # Call the constructor of TripsModule
        super(Kappa_Module, self).__init__(argv)
        self.tasks = {'ONT::PERFORM': ['ONT::VERSION']}
        parser = argparse.ArgumentParser()
        parser.add_argument("--kappa_url"
                           ,help="kappa endpoint")
        args = parser.parse_args()
        if args.kappa_url:
            self.kappa_url=args.kappa_url

    def init(self):
        '''
        Initialize Kappa module
        '''
        super(Kappa_Module, self).init()
        # Send subscribe messages
        for task, subtasks in self.tasks.iteritems():
            for subtask in subtasks:
                msg_txt = '(subscribe :content (request &key :content ' +\
                    '(%s &key :content (%s . *))))' % (task, subtask)
                self.send(KQMLPerformative.fromString(msg_txt))
        # Instantiate a singleton DTDA agent
        self.kappa = KappaRuntime(self.kappa_url)
        # Send ready message
        self.ready()

    def receive_request(self, msg, content):
        '''
        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        "tell" message is then sent back.
        '''
        print msg
        content_list = cast(KQMLList, content)
        task_str = content_list.get(0).toString().upper()
        if task_str == 'ONT::PERFORM':
            subtask = cast(KQMLList,content_list.getKeywordArg(':content'))
            subtask_str = subtask.get(0).toString().upper()
            if subtask_str == 'ONT::VERSION':
                reply_content = self.respond_version()
            elif subtask_str == 'ONT::PARSE':
                reply_content = self.respond_parse(subtask.get(1))
            elif subtask_str == 'ONT::START':
                reply_content = self.respond_start(subtask.get(1))
            else:
                self.error_reply(msg, 'unknown request subtask ' + subtask_str)
                return
        else:
            self.error_reply(msg, 'unknown request task ' + task_str)
            return
        reply_msg = KQMLPerformative('reply')
        reply_msg.setParameter(':content', cast(KQMLObject, reply_content))
        self.reply(msg, reply_msg)

    def respond_version(self):
        '''
        Response content to version message
        '''
        reply_content = KQMLList()
        response = self.kappa.version()
        response_content = KQMLList.fromString( '' +\
                        '(ONT::KAPPA ' +\
                             '( ONT::VERSION "%s") ' % response['version'] +\
                             '( ONT::BUILD   "%s") ' % response['build']   +\
                        ')')
        reply_content.add(KQMLList(response_content))
        return reply_content
    def response_error(self,error):
        reply_content = KQMLList()
        for e in error:
            error_msg = '"%s"' % str(e).encode('string-escape').replace('"', '\\"')
            reply_content.add(error_msg)
        return reply_content

    def respond_parse(self,request_code):
        '''
        Response content to parse message
        '''
        kappa_string = request_code.toString()[1:-1]
        print 'raw {0}'.format(kappa_string)
        kappa_code = kappa_string.decode('string_escape')
        print 'respond_parse {0}'.format(kappa_code)
        reply_content = KQMLList()
        try: 
            response = self.kappa.parse(kappa_code)
            response_content = KQMLList.fromString('(ONT::KAPPA ( ONT::OK ) )')
            reply_content.add(KQMLList(response_content))
        except RuntimeError as e:
            response_content = KQMLList.fromString( '' +\
                        '(ONT::KAPPA ' +\
                             '( ONT::ERRORS %s) ' % self.response_error(e.errors).toString() +\
                        ')')
            reply_content.add(KQMLList(response_content))
        return reply_content

    def respond_start(self,request_code):
        '''
        Response content to start message
        '''
        kappa_string = request_code.toString()[1:-1]
        print 'raw {0}'.format(kappa_string)
        kappa_code = kappa_string.decode('string_escape')
        print 'respond_parse {0}'.format(kappa_code)
        reply_content = KQMLList()
        try: 
            response = self.kappa.start(kappa_code)
            response_message = '(ONT::KAPPA ( ONT::TOKEN %d ) )' % response
            response_content = KQMLList.fromString(response_message)
            reply_content.add(KQMLList(response_content))
        except RuntimeError as e:
            response_content = KQMLList.fromString( '' +\
                        '(ONT::KAPPA ' +\
                             '( ONT::ERRORS %s) ' % self.response_error(e.errors).toString() +\
                        ')')
            reply_content.add(KQMLList(response_content))
        return reply_content

if __name__ == "__main__":
    dm = Kappa_Module(['-name', 'Kappa'] + sys.argv[1:])
    dm.run()
