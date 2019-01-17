import uuid
import logging
from os import path
from datetime import datetime
from indra.assemblers.html import HtmlAssembler

from bioagents.settings import IMAGE_DIR, TIMESTAMP_PICS

logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('Bioagents')


from indra.assemblers.english import EnglishAssembler
from kqml import KQMLModule, KQMLPerformative, KQMLList


class BioagentException(Exception):
    pass


class Bioagent(KQMLModule):
    """Abstract class for bioagents."""
    name = "Generic Bioagent (Should probably be overwritten)"
    tasks = []

    def __init__(self, **kwargs):
        super(Bioagent, self).__init__(name=self.name, **kwargs)
        self.my_log_file = self._add_log_file()
        for task in self.tasks:
            self.subscribe_request(task)

        self.ready()
        self.start()
        logger.info("%s has started and is ready." % self.name)
        return

    @classmethod
    def _add_log_file(cls):
        log_file_name = '%s.log' % cls.name
        handler = logging.FileHandler(log_file_name)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s: '
                                      '%(name)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return log_file_name

    def receive_tell(self, msg, content):
        tell_content = content[0].to_string().upper()
        if tell_content == 'START-CONVERSATION':
            logger.info('%s resetting' % self.name)

    def receive_request(self, msg, content):
        """Handle request messages and respond.

        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        message is then sent back.
        """
        try:
            content = msg.get('content')
            task = content.head().upper()
            logger.info("%s received request with task: %s" % (self.name, task))
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
            logger.info("%s will perform task %s with method %s."
                        % (self.name, task, resp_name))
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
            return msg, comment

    def make_failure(self, reason=None, description=None):
        msg = KQMLList('FAILURE')
        if reason:
            msg.set('reason', reason)
        if description:
            msg.sets('description', description)
        return msg

    def send_null_provenance(self, stmt, for_what, reason=''):
        """Send out that no provenance could be found for a given Statement."""
        content_fmt = ('<h4>No supporting evidence found for {statement} from '
                       '{cause}{reason}.</h4>')
        content = KQMLList('add-provenance')
        stmt_txt = EnglishAssembler([stmt]).make_model()
        content.sets('html', content_fmt.format(statement=stmt_txt,
                                                cause=for_what, reason=reason))
        return self.tell(content)

    def send_provenance_for_stmts(self, stmt_list, for_what, limit=5):
        """Send out a provenance tell for a list of INDRA Statements.

        The message is used to provide evidence supporting a conclusion.
        """
        logger.info("Sending provenance for %d statements for \"%s\"."
                    % (len(stmt_list), for_what))
        content_fmt = ('<h4>Supporting evidence from the {bioagent} for '
                       '{conclusion}:</h4>\n{evidence}<hr>')
        evidence_html = make_report_cols_html(stmt_list)
        # Actually create the content.
        content = KQMLList('add-provenance')
        content.sets('html',
                     content_fmt.format(conclusion=for_what,
                                        evidence=evidence_html,
                                        bioagent=self.name))
        return self.tell(content)


def make_evidence_html(stmts):
    "Make html from a set of statements."
    ha = HtmlAssembler(stmts)
    return ha.make_model()


def stash_evidence_html(html):
    """Make html for a set of statements, return a link to the file.

    The if the PROVENANCE_LOCATION environment variable determines where the
    content is stored. The variable should be divided by colons, the first
    division indicating whether the file is stored locally or on s3, being
    either "file" or "s3" respectively.

    If the html will be stored locally, the next and last division should be a
    path (absolute would be best) to the location where html files will be
    stored. For example:

        file:/home/myname/projects/cwc-integ/provenance

    If the html will be stored on s3, the next division should be the bucket,
    and the last division should be a prefix to a "directory" where the html
    files will be stored. For example:

        s3:cwc-stuff:bob/provenance

    The default is:

        file:{this directory}/../../../provenance

    Which should land in the cwc-integ directory. If the directory does not yet
    exist, it will be created.
    """
    # Get the provenance location.
    from os import environ, mkdir

    loc = environ.get('PROVENANCE_LOCATION')
    if loc is None:
        this_dir = path.dirname(path.abspath(__file__))
        relpath = path.join(*([this_dir] + 3*[path.pardir] + ['provenance']))
        loc = 'file:' + path.abspath(relpath)
    logger.info("Using provenance location: \"%s\"" % loc)

    # Save the file.
    method = loc.split(':')[0]
    fname = '%s.html' % uuid.uuid4()
    if method == 'file':
        prov_path = loc.split(':')[1]
        if not path.exists(prov_path):
            mkdir(prov_path)
        link = 'file://' + path.join(prov_path, fname)
        with open(link, 'w') as f:
            f.write(html)
    elif method == 's3':
        bucket = loc.split(':')[1]
        prefix = loc.split(':')[2]
        import boto3
        s3 = boto3.client('s3')
        key = prefix + fname
        link = 'https://s3.amazonaws.com/%s/%s' % (bucket, key)
        s3.put_object(Bucket=bucket, Key=key, Body=html.encode('utf-8'),
                      ContentType='text/html')
    else:
        logger.error('Invalid PROVENANCE_LOCATION: "%s". HTML not saved.'
                     % loc)
    return link


def make_report_cols_html(stmt_list):
    """Make columns listing the support given by the statement list."""

    def name(agent):
        return 'None' if agent is None else agent.name

    # Build the list of relevant statements and count their prevalence.
    stmt_rows = {}
    for s in stmt_list:
        # Create a key.
        verb = s.__class__.__name__
        key = (verb,)

        ags = s.agent_list()
        if verb == 'Complex':
            ag_ns = {name(ag) for ag in ags}
            key += tuple(sorted(ag_ns))
        elif verb == 'Conversion':
            subj = name(ags[0])
            objs_from = {name(ag) for ag in ags[1]}
            objs_to = {name(ag) for ag in ags[2]}
            key += (subj, tuple(sorted(objs_from)), tuple(sorted(objs_to)))
        else:
            key += tuple([name(ag) for ag in ags])

        # Update the counts, and add key if needed.
        if key not in stmt_rows.keys():
            stmt_rows[key] = []
        stmt_rows[key].append(s)

    # Build the html.
    rows = []
    for key, stmts in stmt_rows.items():
        stmts_html = make_evidence_html(stmts)
        link = stash_evidence_html(stmts_html)

        count = sum(len(s.evidence) for s in stmts)

        # For now, just skip non-subject-object-verb statements.
        if len(key[1:]) != 2:
            continue

        rows.append('<li>%s %s %s <a href=%s target="_blank">(%d)</a></li>'
                    % (key[1], key[0], key[2], link, count))

    rows.sort()
    return '<ul>%s</ul>' % ('\n'.join(rows))


def get_img_path(img_name):
    """Get a full path for the given image name.

    The name will also have a timestamp added if settings.TIMESTAMP_PICS is
    True. The timestamp, if applied, will prepend the name.
    """
    if TIMESTAMP_PICS:
        date_str = datetime.now().strftime('%Y%m%d%H%M%S')
        img_name = '%s_%s' % (date_str, img_name)
    return path.join(IMAGE_DIR, img_name)
