import sys
import json
import logging
from indra.statements import stmts_from_json
from indra.assemblers import EnglishAssembler
from kqml import *

logger = logging.getLogger('MRA')

class BioNLGModule(KQMLModule):
    def __init__(self, argv):
        super(BioNLGModule, self).__init__(argv)
        self.tasks = ['INDRA-TO-NL']
        for task in self.tasks:
            msg_txt =\
                '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.from_string(msg_txt))
        self.ready()
        super(BioNLGModule, self).start()

    def receive_tell(self, msg, content):
        tell_content = content[0].to_string().upper()
        if tell_content == 'START-CONVERSATION':
            logger.info('BioNLG resetting')

    def receive_request(self, msg, content):
        """Handle request messages and respond.

        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        message is then sent back.
        """
        try:
            content = KQMLPerformative(msg.get_parameter(':content'))
            task_str = content.get_verb()
            logging.info(task_str)
        except Exception as e:
            logger.error('Could not get task string from request.')
            logger.error(e)
            self.error_reply(msg, 'Invalid task')
        try:
            if task_str == 'INDRA-TO-NL':
                reply = self.respond_build_model(content)
            else:
                self.error_reply(msg, 'Unknown task ' + task_str)
                return
        except Exception as e:
            logger.error('Failed to perform task.')
            logger.error(e)
            self.error_reply(msg, 'Failed to perform task')

        reply_msg = KQMLPerformative('reply')
        reply_msg.set_parameter(':content', reply)
        self.reply(msg, reply_msg)

    def respond_build_model(self, content):
        """Return response content to build-model request."""
        model_indra = content.get_parameter(':statements')

        stmts_json_str = get_string_arg(model_indra)
        stmts = decode_indra_stmts(stmts_json_str)
        txt = assemble_english(stmts)

        msg = KQMLPerformative('OK')
        msg.set_parameter(':NL', KQMLString(txt))
        return msg

def decode_indra_stmts(stmts_json_str):
    stmts_json = json.loads(stmts_json_str)
    stmts = stmts_from_json(stmts_json)
    return stmts

def assemble_english(stmts):
    ea = EnglishAssembler(stmts)
    txt = ea.make_model()
    return txt

def get_string_arg(kqml_str):
    if kqml_str is None:
        return None
    s = kqml_str.to_string()
    if s[0] == '"':
        s = s[1:]
    if s[-1] == '"':
        s = s[:-1]
    s = s.replace('\\"', '"')
    return s


if __name__ == "__main__":
    BioNLGModule(['-name', 'BIONLG'] + sys.argv[1:])
