import sys
from jnius import autoclass, cast
from TripsModule import trips_module

KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')

from bioagents.mea import MEA

class MEA_Module(trips_module.TripsModule):
    def __init__(self, argv):
        super(MEA_Module, self).__init__(argv)
        self.tasks = {'ONT::PERFORM': ['ONT::SIMULATE-MODEL']}

    def init(self):
        '''
        Initialize TRIPS module
        '''
        super(MEA_Module, self).init()
        # Send subscribe messages
        for task, subtasks in self.tasks.iteritems():
            for subtask in subtasks:
                msg_txt = '(subscribe :content (request &key :content ' +\
                    '(%s &key :content (%s . *))))' % (task, subtask)
                self.send(KQMLPerformative.fromString(msg_txt))
        # Instantiate a singleton MEA agent
        self.mea = MEA()
        self.ready()

    def receive_request(self, msg, content):
        '''
        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply 
        "tell" message is then sent back.
        '''
        content_list = cast(KQMLList, content)
        task_str = content_list.get(0).toString().upper()
        if task_str == 'ONT::PERFORM':
            subtask = cast(KQMLList,content_list.getKeywordArg(':content'))
            subtask_str = subtask.get(0).toString().upper()
            if subtask_str == 'ONT::SIMULATE-MODEL':
                reply_content = self.respond_simulate_model(content_list)
            else:
                self.error_reply(msg, 'unknown request subtask ' + subtask_str)
                return
        else:
            self.error_reply(msg, 'unknown request task ' + task_str)
            return

        reply_msg = KQMLPerformative('reply')
        reply_msg.setParameter(':content', cast(KQMLObject, reply_content))
        self.reply(msg, reply_msg)
    
    def respond_simulate_model(self, content_list):
        '''
        Response content to simulate-model request
        '''
        # TODO: implement
        reply_content = KQMLList()
        reply_content.add('()')
        return reply_content
    
if __name__ == "__main__":
    MEA_Module(['-name', 'MEA'] + sys.argv[1:]).run()

