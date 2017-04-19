import sys
import json
import logging
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('BIONLG')
from indra.statements import stmts_from_json
from indra.assemblers import EnglishAssembler
from kqml import *


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
            content = msg.get('content')
            task_str = content.head()
            logger.info(task_str)
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
            reply = KQMLList.from_string('(FAILURE NL_GENERATION_ERROR)')

        reply_msg = KQMLPerformative('reply')
        reply_msg.set('content', reply)
        self.reply(msg, reply_msg)

    def respond_build_model(self, content):
        """Return response content to build-model request."""
        stmts_json_str = content.gets('statements')
        stmts = decode_indra_stmts(stmts_json_str)
        txts = assemble_english(stmts)
        txts_kqml = [KQMLString(txt) for txt in txts]
        txts_list = KQMLList(txts_kqml)
        msg = KQMLPerformative('OK')
        msg.set('NL', txts_list)
        return msg

def decode_indra_stmts(stmts_json_str):
    stmts_json = json.loads(stmts_json_str)
    stmts = stmts_from_json(stmts_json)
    return stmts

def assemble_english(stmts):
    txts = []
    for stmt in stmts:
        ea = EnglishAssembler([stmt])
        txt = ea.make_model()
        if txt and txt[-1] == '.':
            txt = txt[:-1]
            txts.append(txt)
    return txts

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
