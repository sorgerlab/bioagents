import sys
import traceback
import os
import subprocess
import base64
import pysb.export
import logging
from bioagents.trips import trips_module
from pysb.tools import render_reactions
from pysb import Parameter
from mra import MRA
from indra.assemblers import pysb_assembler

from bioagents.trips.kqml_performative import KQMLPerformative
from bioagents.trips.kqml_list import KQMLList

logger = logging.getLogger('MRA')

class MRA_Module(trips_module.TripsModule):
    def __init__(self, argv):
        super(MRA_Module, self).__init__(argv)
        self.tasks = ['BUILD-MODEL', 'EXPAND-MODEL']
        self.models = []
        for task in self.tasks:
            msg_txt =\
                '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.from_string(msg_txt))
        # Instantiate a singleton MRA agent
        self.mra = MRA()
        self.ready()
        super(MRA_Module, self).start()

    def receive_request(self, msg, content):
        '''
        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        "tell" message is then sent back.
        '''
        try:
            task_str = content[0].to_string().upper()
        except Exception as e:
            logger.error('Could not get task string from request.')
            logger.error(e)
            self.error_reply(msg, 'Invalid task')
        if task_str == 'BUILD-MODEL':
            try:
                reply_content = self.respond_build_model(content)
            except InvalidModelDescriptionError as e:
                logger.error('Invalid model description.')
                logger.error(e)
                fail_msg = '(FAILURE :reason INVALID_DESCRIPTION)'
                reply_content = KQMLList.from_string(fail_msg)
        elif task_str == 'EXPAND-MODEL':
            try:
                reply_content = self.respond_expand_model(content)
            except InvalidModelIdError as e:
                logger.error('Invalid model ID.')
                logger.error(e)
                fail_msg = '(FAILURE :reason INVALID_MODEL_ID)'
                reply_content = KQMLList.from_string(fail_msg)
            except InvalidModelDescriptionError as e:
                logger.error('Invalid model description.')
                logger.error(e)
                fail_msg = '(FAILURE :reason INVALID_DESCRIPTION)'
                reply_content = KQMLList.from_string(fail_msg)
        else:
            self.error_reply(msg, 'Unknown task ' + task_str)
            return
        reply_msg = KQMLPerformative('reply')
        reply_msg.set_parameter(':content', reply_content)
        self.reply(msg, reply_msg)

    def respond_build_model(self, content_list):
        '''
        Response content to build-model request
        '''
        try:
            descr_arg = content_list.get_keyword_arg(':description')
            descr = descr_arg[0].to_string()
            descr = self.decode_description(descr)
            model = self.mra.build_model_from_ekb(descr)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        if model is None:
            raise InvalidModelDescriptionError
        self.get_context(model)
        self.models.append(model)
        model_id = len(self.models)
        model_enc = self.encode_model(model)
        try:
            model_diagram = self.get_model_diagram(model, model_id)
        except DiagramGenerationError as e:
            logger.error('Could not generate model diagram.')
            logger.error(e)
            model_diagram = ''
        except DiagramConversionError as e:
            logger.error('Could not save model diagram.')
            logger.error(e)
            model_diagram = ''
        reply_content =\
            KQMLList.from_string(
            '(SUCCESS :model-id %s :model "%s" :diagram "%s")' %\
                (model_id, model_enc, model_diagram))
        return reply_content

    def respond_expand_model(self, content_list):
        '''
        Response content to expand-model request
        '''
        try:
            descr_arg = content_list.get_keyword_arg(':description')
            descr = descr_arg[0].to_string()
            descr = self.decode_description(descr)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        model_id_arg = content_list.get_keyword_arg(':model-id')
        if model_id_arg is None:
            logger.error('Model ID missing.')
            raise InvalidModelIdError
        try:
            model_id_str = model_id_arg.to_string()
            model_id = int(model_id_str)
        except Exception as e:
            logger.error('Could not get model ID as integer.')
            raise InvalidModelIdError(e)
        if model_id < 1 or model_id > len(self.models):
            logger.error('Model ID does not refer to an existing model.')
            raise InvalidModelIdError

        try:
            model = self.mra.expand_model_from_ekb(descr)
        except Exception as e:
            raise InvalidModelDescriptionError
        self.get_context(model)
        self.models.append(model)
        model_id = len(self.models)
        model_enc = self.encode_model(model)
        try:
            model_diagram = self.get_model_diagram(model, model_id)
        except DiagramGenerationError:
            model_diagram = ''
        except DiagramConversionError:
            model_diagram = ''
        reply_content =\
            KQMLList.from_string(
            '(SUCCESS :model-id %s :model "%s" :diagram "%s")' %\
                (model_id, model_enc, model_diagram))
        return reply_content

    @staticmethod
    def get_model_diagram(model, model_id=None):
        for m in model.monomers:
            pysb_assembler.set_extended_initial_condition(model, m, 0)
        fname = 'model%d' % ('' if model_id is None else model_id)
        try:
            diagram_dot = render_reactions.run(model)
        #TODO: use specific PySB/BNG exceptions and handle them
        # here to show meaningful error messages
        except Exception as e:
            raise DiagramGenerationError(e)
        try:
            with open(fname + '.dot', 'wt') as fh:
                fh.write(diagram_dot)
            subprocess.call(('dot -T png -o %s.png %s.dot' %
                             (fname, fname)).split(' '))
            abs_path = os.path.abspath(os.getcwd())
            if abs_path[-1] != '/':
                abs_path = abs_path + '/'
            full_path = abs_path + fname + '.png'
        except Exception as e:
            raise DiagramConversionError(e)
        return full_path

    @staticmethod
    def get_context(model):
        # TODO: Here we will have to query the context
        # for now it is not used
        pass

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
        model_str = str(model_str.strip())
        model_str = model_str.replace('"', '\\"')
        return model_str

class DiagramGenerationError(Exception):
    pass

class DiagramConversionError(Exception):
    pass

class InvalidModelDescriptionError(Exception):
    pass

class InvalidModelIdError(Exception):
    pass

if __name__ == "__main__":
    MRA_Module(['-name', 'MRA'] + sys.argv[1:])
