import sys
import logging
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('Bioagents')
from itertools import groupby
from collections import defaultdict
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
        logger.info("%s has started and is ready." % self.name)
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
        return

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

    def send_provenance_for_stmts(self, stmt_list, for_what, limit=5):
        """Send out a provenance tell for a list of INDRA Statements.

        The message is used to provide evidence supporting a conclusion.
        """
        content_fmt = ('<h4>Supporting evidence from the {bioagent} for '
                       '{conclusion}:</h4>\n{evidence}<hr>')
        evidence_html = make_evidence_html(stmt_list, limit)
        # Actually create the content.
        content = KQMLList('add-provenance')
        content.sets('html',
                     content_fmt.format(conclusion=for_what,
                                        evidence=evidence_html,
                                        bioagent=self.name))
        return self.tell(content)


def make_evidence_html(stmt_list, limit=5):
    """Creates HTML content for evidences corresponding to INDRA Statements."""
    # Create some formats
    url_base = 'https://www.ncbi.nlm.nih.gov/pubmed/'
    pmid_link_fmt = '<a href={url}{pmid} target="_blank">PMID{pmid}</a>'

    def get_ev_desc(ev, stmt):
        "Get a description of the evidence."
        if ev.text:
            entry = "<i>'%s'</i>" % ev.text
        # If the entry at least has a source ID in a database
        elif ev.source_id:
            entry = "Database entry in '%s': %s" % \
                (ev.source_api, ev.source_id)
        # Otherwise turn it into English
        else:
            txt = EnglishAssembler([stmt]).make_model()
            entry = "Database entry in '%s' representing: %s" % \
                (ev.source_api, txt)
        return entry

    # Extract a list of the evidence then map pmids to lists of text
    evidence_list = {(ev, get_ev_desc(ev, stmt)) for stmt in stmt_list
                     for ev in stmt.evidence}
    evidence_with_text = {(ev, txt) for ev, txt in evidence_list if ev.text}
    evidence_from_db = {(ev, txt) for ev, txt in evidence_list if not ev.text
                        and ev.source_id}
    evidence_no_ids = {(ev, txt) for ev, txt in evidence_list if (ev not in
                       evidence_with_text) and (ev not in evidence_from_db)}
    evidence_list = evidence_with_text | evidence_from_db | evidence_no_ids
    entries = set()
    for i, (ev, entry) in enumerate(evidence_list):
        if limit and i >= limit:
            break
        if ev.pmid:
            entry += ' (%s)' % (pmid_link_fmt.format(url=url_base,
                                                     pmid=ev.pmid))
        entries.add(entry)

    entries_list = ['<li>%s</li>' % entry for entry in entries]
    evidence_html = '<ul>%s</ul>' % ('\n'.join(entries_list))
    return evidence_html
