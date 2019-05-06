import sys
import json
import logging
from bioagents import Bioagent
from indra.statements import stmts_from_json
from indra.assemblers.english import EnglishAssembler
from kqml import KQMLList, KQMLPerformative, KQMLString


logger = logging.getLogger('BIONLG')
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)


class BioNLG_Module(Bioagent):
    name = 'BioNLG'
    tasks = ['INDRA-TO-NL']

    def receive_request(self, msg, content):
        """Handle request messages and respond.

        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A
        reply_content message is then sent back.
        """
        try:
            content = msg.get('content')
            task_str = content.head().upper()
            logger.info(task_str)
        except Exception as e:
            logger.error('Could not get task string from request.')
            logger.error(e)
            return self.error_reply(msg, 'Invalid task')
        try:
            if task_str == 'INDRA-TO-NL':
                reply_content = self.respond_indra_to_nl(content)
            else:
                return self.error_reply(msg, 'Unknown task ' + task_str)
        except Exception as e:
            logger.error('Failed to perform task.')
            logger.error(e)
            reply_content = KQMLList('FAILURE')
            reply_content.set('reason', 'NL_GENERATION_ERROR')

        return self.reply_with_content(msg, reply_content)

    def respond_indra_to_nl(self, content):
        """Return response content to build-model request."""
        stmts_cl_json = content.get('statements')
        stmts = stmts_from_cl_json(stmts_cl_json)
        txts = assemble_english(stmts)
        txts_kqml = [KQMLString(txt) for txt in txts]
        txts_list = KQMLList(txts_kqml)
        reply = KQMLList('OK')
        reply.set('NL', txts_list)
        return reply


def stmts_from_cl_json(stmts_cl_json):
    stmts = [Bioagent.get_statement(cl_stmt) for cl_stmt in stmts_cl_json]
    return stmts


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


if __name__ == "__main__":
    BioNLG_Module(argv=sys.argv[1:])
