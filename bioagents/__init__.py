import sys
import logging
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('Bioagents')

from indra.assemblers import EnglishAssembler
from kqml import KQMLModule, KQMLPerformative, KQMLList


class BioagentException(Exception):
    pass


class Bioagent(KQMLModule):
    """Abstract class for bioagents."""
    name = "Generic Bioagent (Should probably be overwritten)"
    tasks = []

    def __init__(self, **kwargs):
        super(Bioagent, self).__init__(name=self.name, **kwargs)
        for task in self.tasks:
            self.subscribe_request(task)

        self.ready()
        self.start()
        logger.info("%s is has started and ready." % self.name)
        return

    def receive_request(self, msg, content):
        """Handle request messages and respond.

        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        message is then sent back.
        """
        try:
            content = msg.get('content')
            task = content.head().upper()
        except Exception as e:
            logger.error('Could not get task string from request.')
            logger.error(e)
            reply_content = self.make_failure('INVALID_REQUEST')
            return self.reply_with_content(msg, reply_content)

        if task in self.tasks:
            reply_content = self._respond_to(task, content)
        else:
            logger.error('Could not perform task.')
            logger.error("Task %s not found in %s." %
                         (task, str(self.tasks)))
            reply_content = self.make_failure('UNKNOWN_TASK')

        return self.reply_with_content(msg, reply_content)

    def _respond_to(self, task, content):
        """Get the method to responsd to the task indicated by task."""
        resp_name = "respond_" + task.replace('-', '_').lower()
        try:
            resp = getattr(self, resp_name)
        except AttributeError:
            logger.error("Tried to execute unimplemented task.")
            logger.error("Did not find response method %s." % resp_name)
            return self.make_failure('INVALID_TASK')
        try:
            reply_content = resp(content)
            return reply_content
        except BioagentException:
            raise
        except Exception as e:
            logger.error('Could not perform response to %s' % task)
            logger.exception(e)
            return self.make_failure('INTERNAL_FAILURE')

    def reply_with_content(self, msg, reply_content):
        """A wrapper around the reply method from KQMLModule."""
        reply_msg = KQMLPerformative('reply')
        reply_msg.set('content', reply_content)
        self.reply(msg, reply_msg)
        return (msg, reply_content)

    def tell(self, content):
        """Send a tell message."""
        msg = KQMLPerformative('tell')
        msg.set('content', content)
        return self.send(msg)

    def error_reply(self, msg, comment):
        if not self.testing:
            return KQMLModule.error_reply(self, msg, comment)
        else:
            return (msg, comment)

    def make_failure(self, reason=None, description=None):
        msg = KQMLList('FAILURE')
        if reason:
            msg.set('reason', reason)
        if description:
            msg.sets('description', description)
        return msg

    def add_provenance_for_stmts(self, stmt_list, for_what, with_stmt=False,
                                 with_belief=False):
        """Creates the content for an add-provenance tell message.

        The message is used to provide evidence supporting the conclusion.
        """
        # Create some formats
        url_base = 'https://www.ncbi.nlm.nih.gov/pubmed/?term'
        stmt_evidence_fmt = ('Found at pmid <a href={url}={pmid} '
                             'target="_blank">{pmid}</a>:\n<ul>{evidence}\n'
                             '</ul>')
        content_fmt = ('<h4>Supporting evidence from the {bioagent} for '
                       '\'{conclusion}\':</h4>\n{evidence}<hr>')

        def translate_stmt(stmt):
            if not with_stmt:
                return ''
            ret = '%s' % EnglishAssembler([stmt]).make_model()
            if with_belief:
                ret += ' (belief: %s)' % stmt.belief
            ret += ': '
            return ret

        # Extract a list of the evidence then map pmids to lists of text
        evidence_tpl_lst = [(translate_stmt(stmt), ev)
                            for stmt in stmt_list for ev in stmt.evidence]
        pmid_set = set([ev.pmid for _, ev in evidence_tpl_lst])
        pmid_text_dict = {
            pmid: [stmt + "<i>\'%s\'</i>" % ev.text
                   for stmt, ev in evidence_tpl_lst if ev.pmid == pmid]
            for pmid in pmid_set
            }

        # Create the text for displaying the evidence.
        evidence_text = '\n'.join([
            stmt_evidence_fmt.format(
                url=url_base,
                pmid=pmid,
                evidence='\n'.join(['<li>%s</li>' % txt for txt in txt_list])
                )
            for pmid, txt_list in pmid_text_dict.items()
            ])

        # Actually create the content.
        content = KQMLList('add-provenance')
        content.sets(
            'html',
            content_fmt.format(
                conclusion=for_what,
                evidence=evidence_text,
                bioagent=self.name)
            )
        return self.tell(content)
