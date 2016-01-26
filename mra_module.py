import sys
from jnius import autoclass, cast
from TripsModule import trips_module

KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')

from mra import MRA

class MRA_Module(trips_module.TripsModule):
    def __init__(self, argv):
        super(MRA_Module, self).__init__(argv)
        self.tasks = {'ONT::PERFORM': ['ONT::BUILD-MODEL', 'ONT::EXPAND-MODEL']}

    def init(self):
        '''
        Initialize TRIPS module
        '''
        super(MRA_Module, self).init()
        # Send subscribe messages
        for task, subtasks in self.tasks.iteritems():
            for subtask in subtasks:
                msg_txt = '(subscribe :content (request &key :content ' +\
                    '(%s &key :content (%s . *))))' % (task, subtask)
                self.send(KQMLPerformative.fromString(msg_txt))
        # Instantiate a singleton MRA agent
        self.mra = MRA()
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
            if subtask_str == 'ONT::BUILD-MODEL':
                reply_content = self.respond_build_model(content_list)
            elif subtask_str == 'ONT::EXPAND-MODEL':
                reply_content = self.respond_expand_model(content_list)
            else:
                self.error_reply(msg, 'unknown request subtask ' + subtask_str)
                return
        else:
            self.error_reply(msg, 'unknown request task ' + task_str)
            return

        reply_msg = KQMLPerformative('reply')
        reply_msg.setParameter(':content', cast(KQMLObject, reply_content))
        self.reply(msg, reply_msg)
    
    def respond_build_model(self, content_list):
        '''
        Response content to build-model request
        '''
        # TODO: get parameters from content
        model_txt = 'KRAS activates Raf and Raf activates Erk.'
        model = mra.build_model_from_text(model_txt)
        reply_content = KQMLList()
        reply_content.add(model)
        return reply_content
    
    def respond_expand_model(self, content_list):
        '''
        Response content to expand-model request
        '''
        # TODO: implement
        model_txt = 'Vemurafenib inactivates Raf.'
        model = mra.expand_model_from_text(model_txt)
        reply_content = KQMLList()
        reply_content.add(model)
        return reply_content

if __name__ == "__main__":
    MRA_Module(['-name', 'MRA'] + sys.argv[1:]).run()

