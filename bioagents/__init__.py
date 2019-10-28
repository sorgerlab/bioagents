import uuid
import logging
from os import path
from datetime import datetime

from indra.statements import Agent, Statement, stmts_from_json
from indra.assemblers.html import HtmlAssembler
from indra.util.statement_presentation import group_and_sort_statements, \
    make_string_from_sort_key

from bioagents.settings import IMAGE_DIR, TIMESTAMP_PICS
from kqml.cl_json import CLJsonConverter

logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('Bioagents')


from indra.assemblers.english import EnglishAssembler
from kqml import KQMLModule, KQMLPerformative, KQMLList, KQMLString


class BioagentException(Exception):
    pass


class Bioagent(KQMLModule):
    """Abstract class for bioagents."""
    name = "Generic Bioagent (Should probably be overwritten)"
    tasks = []
    converter = CLJsonConverter(token_bools=True)

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

    @classmethod
    def get_agent(cls, cl_agent):
        """Get an agent from the kqml cl-json representation (KQMLList)."""
        agent_json = cls.converter.cl_to_json(cl_agent)
        if isinstance(agent_json, list):
            return [ensure_agent_type(Agent._from_json(agj))
                    for agj in agent_json]
        else:
            return ensure_agent_type(Agent._from_json(agent_json))

    @classmethod
    def get_statement(cls, cl_statement):
        """Get an INDRA Statement from cl-json"""
        stmt_json = cls.converter.cl_to_json(cl_statement)
        if not stmt_json:
            return None
        elif isinstance(stmt_json, list):
            return stmts_from_json(stmt_json)
        else:
            return Statement._from_json(stmt_json)

    @classmethod
    def make_cljson(cls, entity):
        """Convert an Agent or a Statement into cljson.

        `entity` is expected to have a method `to_json` which returns valid
        json.
        """
        # Regularize the input to plain JSON
        if isinstance(entity, list):
            entity_json = [e.to_json() if hasattr(e, 'to_json')
                           else e  # assumed to be a list or a dict.
                           for e in entity]
        elif hasattr(entity, 'to_json'):
            entity_json = entity.to_json()
        else:  # Assumed to be a jsonifiable dict.
            entity_json = entity.copy()
        return cls.converter.cl_from_json(entity_json)

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
            return self.make_failure('INTERNAL_FAILURE', description=str(e))

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

    def request(self, content):
        """Send a request message."""
        msg = KQMLPerformative('request')
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

    def send_provenance_for_stmts(self, stmt_list, for_what, limit=50,
                                  ev_counts=None, source_counts=None):
        """Send out a provenance tell for a list of INDRA Statements.

        The message is used to provide evidence supporting a conclusion.
        """
        logger.info("Sending provenance for %d statements for \"%s\"."
                    % (len(stmt_list), for_what))
        title = "Supporting evidence for %s" % for_what
        content_fmt = '<h4>%s (max %s):</h4>\n%s<hr>'
        evidence_html = self._make_report_cols_html(stmt_list, limit=limit,
                                                    ev_counts=ev_counts,
                                                    source_counts=source_counts,
                                                    title=title)

        content = KQMLList('add-provenance')
        content.sets('html', content_fmt % (title, limit, evidence_html))
        return self.tell(content)

    def _make_evidence_html(self, stmts, ev_counts=None, source_counts=None,
                            title='Results from the INDRA database'):
        "Make html from a set of statements."
        ha = HtmlAssembler(stmts, db_rest_url='db.indra.bio', title=title,
                           ev_totals=ev_counts, source_counts=source_counts)
        return ha.make_model()

    def _stash_evidence_html(self, html):
        """Make html for a set of statements, return a link to the file.

        The if the PROVENANCE_LOCATION environment variable determines where
        the content is stored. The variable should be divided by colons, the
        first division indicating whether the file is stored locally or on s3,
        being either "file" or "s3" respectively.

        If the html will be stored locally, the next and last division should
        be a path (absolute would be best) to the location where html files
        will be stored. For example:

            file:/home/myname/projects/cwc-integ/provenance

        If the html will be stored on s3, the next division should be the
        bucket, and the last division should be a prefix to a "directory" where
        the html files will be stored. For example:

            s3:cwc-stuff:bob/provenance

        The default is:

            file:{this directory}/../../../provenance

        Which should land in the cwc-integ directory. If the directory does not
        yet exist, it will be created.
        """
        # Get the provenance location.
        from os import environ, mkdir

        loc = environ.get('PROVENANCE_LOCATION')
        if loc is None:
            this_dir = path.dirname(path.abspath(__file__))
            rel = path.join(*([this_dir] + 3*[path.pardir] + ['provenance']))
            loc = 'file:' + path.abspath(rel)
        logger.info("Using provenance location: \"%s\"" % loc)

        # Save the file.
        method = loc.split(':')[0]
        fname = '%s.html' % uuid.uuid4()
        if method == 'file':
            prov_path = loc.split(':')[1]
            if not path.exists(prov_path):
                mkdir(prov_path)
            fpath = path.join(prov_path, fname)
            with open(fpath, 'w') as f:
                f.write(html)
            link = fpath
        elif method == 's3':
            bucket = loc.split(':')[1]
            prefix = loc.split(':')[2]

            # Get a connection to s3.
            import boto3
            from botocore import UNSIGNED
            from botocore.client import Config
            s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))

            key = prefix + fname
            link = 'https://s3.amazonaws.com/%s/%s' % (bucket, key)
            s3.put_object(Bucket=bucket, Key=key, Body=html.encode('utf-8'),
                          ContentType='text/html')
        else:
            logger.error('Invalid PROVENANCE_LOCATION: "%s". HTML not saved.'
                         % loc)
            link = None
        return link

    def say(self, message):
        """Say something to the user."""
        if message:
            msg = KQMLList('say')
            msg.append(KQMLString(message))
            self.request(msg)

    def _make_report_cols_html(self, stmt_list, limit=5, ev_counts=None,
                               source_counts=None, **kwargs):
        """Make columns listing the support given by the statement list."""
        if not stmt_list:
            return "No statements found."

        def href(ref, text):
            return '<a href=%s target="_blank">%s</a>' % (ref, text)

        # Build the list of relevant statements and count their prevalence.
        sorted_groups = group_and_sort_statements(stmt_list,
                                                  ev_totals=ev_counts,
                                                  source_counts=source_counts)

        # Build the html.
        lines = []
        for group in sorted_groups[:limit]:
            if source_counts is None:
                key, verb, stmts = group
            else:
                key, verb, stmts, arg_counts, group_source_counts = group
            count = key[2]
            line = '<li>%s %s</li>' % (make_string_from_sort_key(key, verb),
                                       '(%d)' % count)
            lines.append(line)

        # Build the overall html.
        list_html = '<ul>%s</ul>' % ('\n'.join(lines))
        html = self._make_evidence_html(stmt_list, ev_counts=ev_counts,
                                        source_counts=source_counts, **kwargs)
        link = self._stash_evidence_html(html)
        if link is None:
            link_html = 'I could not generate the full list.'
        elif link.startswith('http'):
            link_html = href(link, 'Here') + ' is the full list.'
        else:
            link_html = 'Here: %s is the full list.' % link

        return list_html + '\n' + link_html


def get_img_path(img_name):
    """Get a full path for the given image name.

    The name will also have a timestamp added if settings.TIMESTAMP_PICS is
    True. The timestamp, if applied, will prepend the name.
    """
    if TIMESTAMP_PICS:
        date_str = datetime.now().strftime('%Y%m%d%H%M%S')
        img_name = '%s_%s' % (date_str, img_name)
    return path.join(IMAGE_DIR, img_name)


def infer_agent_type(agent):
    if 'FPLX' in agent.db_refs:
        return 'ONT::PROTEIN-FAMILY'
    elif 'HGNC' in agent.db_refs or 'UP' in agent.db_refs:
        return 'ONT::GENE-PROTEIN'
    elif 'CHEBI' in agent.db_refs or 'PUBCHEM' in agent.db_refs:
        return 'ONT::PHARMACOLOGIC-SUBSTANCE'
    elif 'GO' in agent.db_refs or 'MESH' in agent.db_refs:
        return 'ONT::BIOLOGICAL-PROCESS'
    return None


def add_agent_type(agent):
    if agent is None:
        return None
    inferred_type = infer_agent_type(agent)
    if inferred_type:
        agent.db_refs['TYPE'] = inferred_type
    return agent


def ensure_agent_type(agent):
    if agent is None:
        return None

    if 'TYPE' not in agent.db_refs.keys():
        return add_agent_type(agent)
    else:
        return agent
