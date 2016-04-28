import sys
import traceback
import os
import subprocess
import base64
import pysb.export
from jnius import autoclass, cast
from TripsModule import trips_module
from pysb.tools import render_reactions
from pysb import Parameter
from mra import MRA

KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')


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
            msg_txt =\
                '(subscribe :content (request &key :content (%s . *)))' % task
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
        model = self.mra.build_model_from_ekb(descr)
        if model is None:
            reply_content =\
                KQMLList.fromString('(FAILURE :reason INVALID_DESCRIPTION)')
            return reply_content
        self.get_context(model)
        self.models.append(model)
        model_id = len(self.models)
        model_enc = self.encode_model(model)
        model_diagram = self.get_model_diagram(model, model_id)
        reply_content =\
            KQMLList.fromString(
            '(SUCCESS :model-id %s :model "%s" :diagram "%s")' %\
                (model_id, model_enc, model_diagram))
        return reply_content

    def respond_expand_model(self, content_list):
        '''
        Response content to expand-model request
        '''
        descr_arg = cast(KQMLList, content_list.getKeywordArg(':description'))
        descr = descr_arg.get(0).toString()
        descr = self.decode_description(descr)

        model_id_arg = cast(KQMLList,
                            content_list.getKeywordArg(':model-id'))
        model_id_str = model_id_arg.toString()
        try:
            model_id = int(model_id_str)
        except ValueError:
            reply_content =\
                KQMLList.fromString('(FAILURE :reason INVALID_MODEL_ID)')
            return reply_content
        if model_id < 1 or model_id > len(self.models):
            reply_content =\
                KQMLList.fromString('(FAILURE :reason INVALID_MODEL_ID)')
            return reply_content

        model = self.mra.expand_model_from_ekb(descr)
        self.get_context(model)
        self.models.append(model)
        model_id = len(self.models)
        model_enc = self.encode_model(model)
        model_diagram = self.get_model_diagram(model, model_id)
        reply_content =\
            KQMLList.fromString(
            '(SUCCESS :model-id %s :model "%s" :diagram "%s")' %\
                (model_id, model_enc, model_diagram))
        return reply_content

    @staticmethod
    def get_model_diagram(model, model_id=None):
        fname = 'model%d' % ('' if model_id is None else model_id)
        try:
            diagram_dot = render_reactions.run(model)
        #TODO: use specific PySB/BNG exceptions and handle them
        # here to show meaningful error messages
        except:
            #traceback.print_exc()
            return ''
        with open(fname + '.dot', 'wt') as fh:
            fh.write(diagram_dot)
        subprocess.call(('dot -T png -o %s.png %s.dot' %
                         (fname, fname)).split(' '))
        abs_path = os.path.abspath(os.path.dirname(__file__))
        if abs_path[-1] != '/':
            abs_path = abs_path + '/'
        return abs_path + fname + '.png'

    @staticmethod
    def get_context(model):
        # TODO: Here we will have to query the context
        # for now it is hard coded
        try:
            kras = model.monomers['KRAS']
            p = Parameter('kras_act_0', 100)
            model.add_component(p)
            model.initial(kras(act='active'), p)
        except:
            return

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
        model_str = str(model_str)
        b64str = base64.b64encode(model_str)
        return b64str

if __name__ == "__main__":
    m = MRA_Module(['-name', 'MRA'] + sys.argv[1:])
    m.start()
    m.join()
