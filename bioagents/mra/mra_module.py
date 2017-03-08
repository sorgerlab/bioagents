import sys
import json
import logging
import pysb.export
from indra.statements import stmts_to_json
from kqml import *
from mra import MRA

logger = logging.getLogger('MRA')

class MRA_Module(KQMLModule):
    def __init__(self, argv):
        super(MRA_Module, self).__init__(argv)
        self.tasks = ['BUILD-MODEL', 'EXPAND-MODEL', 'MODEL-HAS-MECHANISM',
                      'MODEL-REPLACE-MECHANISM', 'MODEL-REMOVE-MECHANISM',
                      'MODEL-UNDO']
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
            content = KQMLPerformative(msg.get_parameter(':content'))
            task_str = content.get_verb()
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

    def respond_build_model(self, content):
        """Return response content to build-model request."""
        ekb = self._get_model_descr(content, ':description')
        try:
            res = self.mra.build_model_from_ekb(ekb)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        model_id = res.get('model_id')
        if model_id is None:
            raise InvalidModelDescriptionError()
        # Start a SUCCESS message
        msg = KQMLPerformative('SUCCESS')
        # Add the model id
        msg.set_parameter(':model-id', KQMLToken(str(model_id)))
        # Add the INDRA model json
        model = res.get('model')
        model_msg = encode_indra_stmts(model)
        msg.set_parameter(':model', KQMLString(model_msg))
        # Add the natural language model
        model_nl = res.get('model_nl')
        if model_nl:
            msg.set_parameter(':model-nl', KQMLString(model_nl))
        # Add the diagram
        diagram = res.get('diagram')
        if diagram:
            msg.set_parameter(':diagram', KQMLString(diagram))
        else:
            msg.set_parameter(':diagram', KQMLString(''))
        ambiguities = res.get('ambiguities')
        if ambiguities:
            sa = []
            for term_id, ambiguity in ambiguities.items():
                pr = ambiguity[0]['preferred']
                pr_dbids = '|'.join(['::'.join((k, v)) for
                                     k, v in pr['refs'].items()])
                # TODO: once available, replace with real ont type
                pr_type = 'ONT::PROTEIN'
                s1 = '(term :ont-type %s :ids "%s" :name "%s")' % \
                    (pr_type, pr_dbids, pr['name'])
                alt = ambiguity[0]['alternative']
                alt_dbids = '|'.join(['::'.join((k, v)) for
                                      k, v in alt['refs'].items()])
                # TODO: once available, replace with real ont type
                alt_type = 'ONT::PROTEIN-FAMILY'
                s2 = '(term :ont-type %s :ids "%s" :name "%s")' % \
                    (alt_type, alt_dbids, alt['name'])
                s = '(%s :preferred %s :alternative %s)' % \
                    (term_id, s1, s2)
                sa.append(s)
            ambiguities_msg = KQMLList.from_string('(' + ' '.join(sa) + ')')
            msg.set_parameter(':ambiguities', ambiguities_msg)
        return msg

    def respond_expand_model(self, content):
        """Return response content to expand-model request."""
        ekb = self._get_model_descr(content, ':description')
        model_id = self._get_model_id(content)
        try:
            res = self.mra.expand_model_from_ekb(ekb, model_id)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        new_model_id = res.get('model_id')
        if new_model_id is None:
            raise InvalidModelDescriptionError()
        # Start a SUCCESS message
        msg = KQMLPerformative('SUCCESS')
        # Add the model id
        msg.set_parameter(':model-id', KQMLToken(str(new_model_id)))
        # Add the INDRA model json
        model = res.get('model')
        model_msg = encode_indra_stmts(model)
        msg.set_parameter(':model', KQMLString(model_msg))
        # Add the INDRA model new json
        model_new = res.get('model_new')
        if model_new:
            model_new_msg = encode_indra_stmts(model_new)
            msg.set_parameter(':model-new', KQMLString(model_new_msg))
        # Add the natural language model
        model_nl = res.get('model_nl')
        if model_nl:
            msg.set_parameter(':model-nl', KQMLString(model_nl))
        # Add the natural language new model
        model_nl_new = res.get('model_nl_new')
        if model_nl_new:
            msg.set_parameter(':model-nl-new', KQMLString(model_nl_new))
        # Add the diagram
        diagram = res.get('diagram')
        if diagram:
            msg.set_parameter(':diagram', KQMLString(diagram))
        else:
            msg.set_parameter(':diagram', KQMLString(''))
        return msg

    def respond_has_mechanism(self, content):
        """Return response content to model-has-mechanism request."""
        ekb = self._get_model_descr(content, ':description')
        model_id = self._get_model_id(content)
        try:
            res = self.mra.has_mechanism(ekb, model_id)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        # Start a SUCCESS message
        msg = KQMLPerformative('SUCCESS')
        # Add the model id
        msg.set_parameter(':model-id', KQMLToken(str(model_id)))
        # Add TRUE or FALSE for has-mechanism
        has_mechanism_msg = KQMLToken('TRUE' if res['has_mechanism'] else 'FALSE')
        msg.set_parameter(':has-mechanism', has_mechanism_msg)
        query = res.get('query')
        if query:
            query_msg = encode_indra_stmts([query])
            msg.set_parameter(':query', KQMLString(query_msg))
        query_nl = res.get('query_nl')
        if query_nl:
            msg.set_parameter(':query-nl', KQMLString(query_nl))
        return msg

    def respond_remove_mechanism(self, content):
        """Return response content to model-remove-mechanism request."""
        ekb = self._get_model_descr(content, ':description')
        model_id = self._get_model_id(content)
        try:
            res = self.mra.remove_mechanism(ekb, model_id)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        model_id = res.get('model_id')
        if model_id is None:
            raise InvalidModelDescriptionError()
        # Start a SUCCESS message
        msg = KQMLPerformative('SUCCESS')
        # Add the model id
        msg.set_parameter(':model-id', KQMLToken(str(model_id)))
        # Add the INDRA model json
        model = res.get('model')
        model_msg = encode_indra_stmts(model)
        msg.set_parameter(':model', KQMLString(model_msg))
        # Add the natural language model
        model_nl = res.get('model_nl')
        if model_nl:
            msg.set_parameter(':model-nl', KQMLString(model_nl))
        # Add the removed statements
        removed = res.get('removed')
        if removed:
            removed_msg = encode_indra_stmts(removed)
            msg.set_parameter(':removed', KQMLString(removed_msg))
        # Add the removed natural language statements
        removed_nl = res.get('removed_nl')
        if removed_nl:
            msg.set_parameter(':removed-nl', KQMLString(removed_nl))
        # Add the diagram
        diagram = res.get('diagram')
        if diagram:
            msg.set_parameter(':diagram', KQMLString(diagram))
        else:
            msg.set_parameter(':diagram', KQMLString(''))
        return msg

    @staticmethod
    def _get_model_descr(content, arg_name):
        try:
            descr_arg = content.get_parameter(arg_name)
            descr = descr_arg[0].to_string()
            if descr[0] == '"':
                descr = descr[1:]
            if descr[-1] == '"':
                descr = descr[:-1]
            descr = descr.replace('\\"', '"')
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        return descr

    def _get_model_id(self, content):
        model_id_arg = content.get_parameter(':model-id')
        if model_id_arg is None:
            logger.error('Model ID missing.')
            raise InvalidModelIdError
        try:
            model_id_str = model_id_arg.to_string()
            model_id = int(model_id_str)
        except Exception as e:
            logger.error('Could not get model ID as integer.')
            raise InvalidModelIdError(e)
        if not self.mra.has_id(model_id):
            logger.error('Model ID does not refer to an existing model.')
            raise InvalidModelIdError
        return model_id


class InvalidModelDescriptionError(Exception):
    pass


class InvalidModelIdError(Exception):
    pass


def encode_pysb_model(pysb_model):
    model_str = pysb.export.export(pysb_model, 'pysb_flat')
    model_str = str(model_str.strip())
    return model_str


def encode_indra_stmts(stmts):
    stmts_json = stmts_to_json(stmts)
    json_str = json.dumps(stmts_json)
    return json_str

if __name__ == "__main__":
    MRA_Module(['-name', 'MRA'] + sys.argv[1:])
