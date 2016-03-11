import sys
import base64
from jnius import autoclass, cast
from TripsModule import trips_module
import pysb.export

KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')

from mra import MRA

class MRA_Module(trips_module.TripsModule):
    def __init__(self, argv):
        super(MRA_Module, self).__init__(argv)
        self.tasks = ['BUILD-MODEL', 'EXPAND-MODEL']
        self.models = []

    def init(self):
        '''
        Initialize TRIPS module
        '''
        super(MRA_Module, self).init()
        # Send subscribe messages
        for task in self.tasks:
            msg_txt = '(subscribe :content (request &key :content (%s . *)))' % task
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
        if task_str == 'BUILD-MODEL':
            reply_content = self.respond_build_model(content_list)
        elif task_str == 'EXPAND-MODEL':
            reply_content = self.respond_expand_model(content_list)
        else:
            self.error_reply(msg, 'unknown task ' + task_str)
            return
        reply_msg = KQMLPerformative('reply')
        reply_msg.setParameter(':content', cast(KQMLObject, reply_content))
        self.reply(msg, reply_msg)
    
    def respond_build_model(self, content_list):
        '''
        Response content to build-model request
        '''
        descr_arg = cast(KQMLList, content_list.getKeywordArg(':description'))
        descr = descr_arg.get(0).toString()
        descr = self.decode_description(descr)
        print descr
        model = self.mra.build_model_from_ekb(descr)
        if model is None:
            reply_content =\
                KQMLList.fromString('(FAILURE :reason INVALID_DESCRIPTION)')
            return reply_content
        self.models.append(model)
        model_id = len(self.models)
        model_enc = self.encode_model(model)
        reply_content =\
            KQMLList.fromString(
            '(SUCCESS :model-id %s :model (%s))' % (model_id, model_enc))
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
    
    @staticmethod
    def decode_description(descr):
        if descr[0] == '"':
            descr = descr[1:]
        if descr[-1] == '"':
            descr = descr[:-1]
        descr = descr.replace('\\"', '"')
        return descr

    @staticmethod
    def encode_model(model):
        model_str = pysb.export.export(model, 'pysb_flat')
        b64str = base64.b64encode(model_str)
        return b64str

if __name__ == "__main__":
    MRA_Module(['-name', 'MRA'] + sys.argv[1:]).run()

