import os
import sys
import logging
import subprocess

import pysb.export
from pysb.tools import render_reactions
from indra.assemblers import pysb_assembler

from mra import MRA
from kqml import KQMLModule, KQMLPerformative, KQMLList

logger = logging.getLogger('MRA')

class MRA_Module(KQMLModule):
    def __init__(self, argv):
        super(MRA_Module, self).__init__(argv)
        self.tasks = ['BUILD-MODEL', 'EXPAND-MODEL', 'MODEL-HAS-MECHANISM',
                      'MODEL-REPLACE-MECHANISM', 'MODEL-REMOVE-MECHANISM',
                      'MODEL-UNDO']
        self.models = []
        for task in self.tasks:
            msg_txt =\
                '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.from_string(msg_txt))
        # Instantiate a singleton MRA agent
        self.mra = MRA()
        self.ready()
        super(MRA_Module, self).start()

    def receive_tell(self, msg, content):
        tell_content = content[0].to_string().upper()
        if tell_content == 'START-CONVERSATION':
            logger.info('MRA resetting')

    def receive_request(self, msg, content):
        """Handle request messages and respond.

        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        message is then sent back.
        """
        try:
            task_str = content[0].to_string().upper()
        except Exception as e:
            logger.error('Could not get task string from request.')
            logger.error(e)
            self.error_reply(msg, 'Invalid task')
        try:
            if task_str == 'BUILD-MODEL':
                reply_content = self.respond_build_model(content)
            elif task_str == 'EXPAND-MODEL':
                reply_content = self.respond_expand_model(content)
            elif task_str == 'MODEL-HAS-MECHANISM':
                reply_content = self.respond_has_mechanism(content)
            elif task_str == 'MODEL-REMOVE-MECHANISM':
                reply_content = self.respond_remove_mechanism(content)
            else:
                self.error_reply(msg, 'Unknown task ' + task_str)
                return
        except InvalidModelDescriptionError as e:
            logger.error('Invalid model description.')
            logger.error(e)
            fail_msg = '(FAILURE :reason INVALID_DESCRIPTION)'
            reply_content = KQMLList.from_string(fail_msg)
        except InvalidModelIdError as e:
            logger.error('Invalid model ID.')
            logger.error(e)
            fail_msg = '(FAILURE :reason INVALID_MODEL_ID)'
            reply_content = KQMLList.from_string(fail_msg)
        reply_msg = KQMLPerformative('reply')
        reply_msg.set_parameter(':content', reply_content)
        self.reply(msg, reply_msg)

    def respond_build_model(self, content_list):
        """Return response content to build-model request."""
        descr = self._get_model_descr(content_list, ':description')
        try:
            model = self.mra.build_model_from_ekb(descr)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        if model is None:
            raise InvalidModelDescriptionError
        self.get_context(model)
        self.models.append(model)
        new_model_id = len(self.models)
        model_enc = self.encode_model(model)
        model_diagram = self.make_model_diagram(model, new_model_id)
        msg = '(SUCCESS :model-id %s :model "%s" :diagram "%s")' % \
              (new_model_id, model_enc, model_diagram)
        reply_content = KQMLList.from_string(msg)
        return reply_content

    def respond_expand_model(self, content_list):
        """Return response content to expand-model request."""
        descr = self._get_model_descr(content_list, ':description')
        model_id = self._get_model_id(content_list)
        try:
            model = self.mra.expand_model_from_ekb(descr, model_id)
        except Exception as e:
            raise InvalidModelDescriptionError
        self.get_context(model)
        self.models.append(model)
        new_model_id = len(self.models)
        model_enc = self.encode_model(model)
        model_diagram = self.make_model_diagram(model, new_model_id)
        msg = '(SUCCESS :model-id %s :model "%s" :diagram "%s")' % \
              (new_model_id, model_enc, model_diagram)
        reply_content = KQMLList.from_string(msg)
        return reply_content

    def respond_has_mechanism(self, content_list):
        """Return response content to model-has-mechanism request."""
        descr = self._get_model_descr(content_list, ':description')
        model_id = self._get_model_id(content_list)

        try:
            has_mechanism = self.mra.has_mechanism(descr, model_id)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        msg = '(SUCCESS :model-id %s :has-mechanism %s)' % \
              (model_id, has_mechanism)
        reply_content = KQMLList.from_string(msg)
        return reply_content

    def respond_remove_mechanism(self, content_list):
        """Return response content to model-remove-mechanism request."""
        descr = self._get_model_descr(content_list, ':description')
        model_id = self._get_model_id(content_list)

        try:
            model = self.mra.remove_mechanism(descr, model_id)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        self.get_context(model)
        self.models.append(model)
        new_model_id = len(self.models)
        model_enc = self.encode_model(model)
        model_diagram = self.make_model_diagram(model, new_model_id)
        msg = '(SUCCESS :model-id %s :model "%s" :diagram "%s")' % \
              (new_model_id, model_enc, model_diagram)
        reply_content = KQMLList.from_string(msg)
        return reply_content

    @staticmethod
    def _get_model_descr(content_list, arg_name):
        try:
            descr_arg = content_list.get_keyword_arg(arg_name)
            descr = descr_arg[0].to_string()
            if descr[0] == '"':
                descr = descr[1:]
            if descr[-1] == '"':
                descr = descr[:-1]
            descr = descr.replace('\\"', '"')
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        return descr

    def _get_model_id(self, content_list):
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
        return model_id

    @staticmethod
    def make_model_diagram(model, model_id=None):
        """Generate a PySB/BNG reaction network as a PNG file."""
        try:
            for m in model.monomers:
                pysb_assembler.set_extended_initial_condition(model, m, 0)
            fname = 'model%d' % ('' if model_id is None else model_id)
            diagram_dot = render_reactions.run(model)
        # TODO: use specific PySB/BNG exceptions and handle them
        # here to show meaningful error messages
        except Exception as e:
            logger.error('Could not generate model diagram.')
            logger.error(e)
            return ''
        try:
            with open(fname + '.dot', 'wt') as fh:
                fh.write(diagram_dot)
            subprocess.call(('dot -T png -o %s.png %s.dot' %
                             (fname, fname)).split(' '))
            abs_path = os.path.abspath(os.getcwd())
            full_path = os.path.join(abs_path, fname + '.png')
        except Exception as e:
            logger.error('Could not save model diagram.')
            logger.error(e)
            return ''
        return full_path

    @staticmethod
    def get_context(model):
        # TODO: Here we will have to query the context
        # for now it is not used
        pass

    @staticmethod
    def encode_model(model):
        model_str = pysb.export.export(model, 'pysb_flat')
        model_str = str(model_str.strip())
        model_str = model_str.replace('"', '\\"')
        return model_str


class InvalidModelDescriptionError(Exception):
    pass


class InvalidModelIdError(Exception):
    pass


if __name__ == "__main__":
    MRA_Module(['-name', 'MRA'] + sys.argv[1:])
