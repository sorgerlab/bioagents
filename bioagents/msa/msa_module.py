import os
import sys
import re
import pickle
import logging
from datetime import datetime
from threading import Thread

logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('MSA-module')

from kqml import KQMLPerformative, KQMLList

from indra import has_config
from indra.assemblers.sbgn import SBGNAssembler
from indra.tools import assemble_corpus as ac

from bioagents import Bioagent

from bioagents.msa.msa import MSA
from bioagents.msa.exceptions import EntityError

if has_config('INDRA_DB_REST_URL') and has_config('INDRA_DB_REST_API_KEY'):
    from indra.sources.indra_db_rest import IndraDBRestAPIError, \
                                            get_statements_for_paper

    CAN_CHECK_STATEMENTS = True
else:
    logger.warning("Database web api not specified. Cannot get background.")
    CAN_CHECK_STATEMENTS = False


def _read_signor_afs():
    path = os.path.dirname(os.path.abspath(__file__)) + \
            '/../resources/signor_active_forms.pkl'
    with open(path, 'rb') as pkl_file:
        stmts = pickle.load(pkl_file)
    if isinstance(stmts, dict):
        signor_afs = []
        for _, stmt_list in stmts.items():
            signor_afs += stmt_list
    else:
        signor_afs = stmts
    return signor_afs


DUMP_LIMIT = 100


class MSALookupError(Exception):
    pass


class MSA_Module(Bioagent):
    name = 'MSA'
    tasks = ['PHOSPHORYLATION-ACTIVATING', 'FIND-RELATIONS-FROM-LITERATURE',
             'GET-PAPER-MODEL', 'CONFIRM-RELATION-FROM-LITERATURE',
             'GET-COMMON']
    signor_afs = _read_signor_afs()

    def __init__(self, *args, **kwargs):
        corpus_config = os.environ.get('CWC_MSA_CORPUS')
        self.msa = MSA(corpus_config=corpus_config)
        super(MSA_Module, self).__init__(*args, **kwargs)
        return

    def respond_get_common(self, content):
        """Find the common up/down streams of a protein."""
        # TODO: This entire function could be part of the MSA.
        if not CAN_CHECK_STATEMENTS:
            return self.make_failure(
                'NO_KNOWLEDGE_ACCESS',
                'Cannot access the database through the web api.'
                )
        genes_cljson = content.get('genes')
        agents = [self.get_agent(ag) for ag in genes_cljson]
        if len(agents) < 2:
            return self.make_failure('NO_TARGET',
                                     'Only %d < 2 agents given.' % len(agents))

        direction = content.gets('up-down')
        logger.info("Got genes: %s and direction %s." % (agents, direction))

        # Choose some parameters based on direction.
        if direction == 'ONT::MORE':
            method = 'common_upstreams'
            prefix = 'up'
        elif direction == 'ONT::SUCCESSOR':
            method = 'common_downstreams'
            prefix = 'down'
        else:
            # TODO: With the new MSA we could handle common neighbors.
            return self.make_failure("UNKNOWN_ACTION", direction)

        # Find the commonalities.
        try:
            finder = self.msa.find_mechanisms(method, *agents)
        except EntityError as e:
            return self.make_failure("MISSING_TARGET", e.args[0])

        # Get post statements to provenance.
        if len(agents) > 2:
            name_list = ', '.join(ag.name for ag in agents[:-1]) + ','
        else:
            name_list = agents[0].name
        name_list += ' and ' + agents[-1].name
        msg = ('%sstreams of ' % prefix).capitalize() + name_list
        self.send_provenance_for_stmts(finder.get_statements(), msg,
            ev_counts=finder.get_ev_totals(),
            source_counts=finder.get_source_counts())

        # Create the reply
        resp = KQMLPerformative('SUCCESS')
        agents = finder.get_other_agents()
        resp.set('entities-found', self.make_cljson(agents))
        resp.sets('prefix', prefix)
        return resp

    def respond_phosphorylation_activating(self, content):
        """Return response content to phosphorylation_activating request."""
        if not CAN_CHECK_STATEMENTS:
            return self.make_failure(
                'NO_KNOWLEDGE_ACCESS',
                'Cannot access the database through the web api.'
                )
        heading = content.head()
        m = re.match(r'(\w+)-(\w+)', heading)
        if m is None:
            return self.make_failure('UNKNOWN_ACTION')
        action, polarity = [s.lower() for s in m.groups()]
        target_cljson = content.get('target')
        if target_cljson is None or not len(target_cljson):
            return self.make_failure('MISSING_TARGET')
        agent = self.get_agent(target_cljson)
        # This is a bug in the BA that we can handle here
        if isinstance(agent, list):
            agent = agent[0]
        logger.debug('Found agent (target): %s.' % agent.name)
        site = content.gets('site')
        if site is None:
            residue = None
            position = None
        else:
            try:
                residue, position = site.split('-')
            except:
                return self.make_failure('INVALID_SITE')

        finder = self.msa.find_phos_activeforms(agent, residue=residue,
                                                position=position,
                                                action=action,
                                                polarity=polarity)
        stmts = finder.get_statements()

        logger.info("Found %d matching statements." % len(stmts))
        if not len(stmts):
            return self.make_failure(
                'MISSING_MECHANISM',
                "Could not find statement matching phosphorylation activating "
                "%s, %s, %s, %s." % (agent.name, residue, position,
                                     'phosphorylation')
                )
        else:
            description = finder.describe(include_negative=False)
            # self.say(description)
            msg = "phosphorylation at %s%s activates %s." \
                  % (residue, position, agent.name)
            self.send_provenance_for_stmts(stmts, msg,
                ev_counts=finder.get_ev_totals(),
                source_counts=finder.get_source_counts())
            msg = KQMLPerformative('SUCCESS')
            msg.set('is-activating', 'TRUE')
            msg.sets('suggestion', description)
            return msg

    def _get_query_info(self, content):
        subj = _get_agent_if_present(content, 'source')
        obj = _get_agent_if_present(content, 'target')
        if not subj and not obj:
            raise MSALookupError('MISSING_MECHANISM')

        kfilter_agents = content.get('filter_agents')
        filter_agents = Bioagent.get_agent(kfilter_agents) if kfilter_agents \
            else []

        kcontext_agents = content.get('context')
        context_agents = Bioagent.get_agent(kcontext_agents) if kcontext_agents \
            else []

        stmt_type = content.gets('type')
        if stmt_type == 'unknown':
            stmt_type = None
        return subj, obj, stmt_type, filter_agents, context_agents

    def _send_provenance_async(self, finder, desc):
        q = finder.query
        nl_input = {k: ag.name if ag else 'unknown'
                    for k, ag in [('subject', q.subj), ('object', q.obj)]}
        nl_input['stmt_type'] = q.stmt_type
        fmt = ('subject={subject}, statement type={stmt_type}, '
               'object={object}')
        nl = fmt.format(**nl_input)
        nl = "%s: %s" % (desc, nl)

        stmts = finder.get_statements(block=False)
        num_stmts = 'no' if stmts is None else len(stmts)
        logger.info("Retrieved %s statements so far. Sending provenance in a "
                    "thread..." % num_stmts)
        try:
            th = Thread(target=self._send_display_stmts, args=(finder, nl))
            th.start()
        except Exception as e:
            logger.warning("Failed to start thread to send provenance.")
            logger.exception(e)
        return

    def respond_find_relations_from_literature(self, content):
        """Find statements matching some subject, verb, object information."""
        try:
            subj, obj, stmt_type, filter_agents, context_agents = \
                self._get_query_info(content)
            finder = \
                self.msa.find_mechanism_from_input(subj, obj, None, stmt_type,
                                                   ev_limit=3, persist=False,
                                                   timeout=5,
                                                   filter_agents=filter_agents,
                                                   context_agents=context_agents)
            self._send_provenance_async(finder,
                                        'finding statements that match')
        except MSALookupError as mle:
            return self.make_failure(mle.args[0])

        stmts = finder.get_statements(timeout=15)
        if stmts is None:
            # Calling this success may be a bit ambitious.
            resp = KQMLPerformative('SUCCESS')
            resp.set('status', 'WORKING')
            resp.set('entities-found', 'nil')
            resp.set('num-relations-found', '0')
            resp.set('dump-limit', str(DUMP_LIMIT))
            return resp

        agents = finder.get_other_agents() \
            if stmts else []
        description = finder.describe(include_negative=False) \
            if stmts else None
        #self.say(description)
        resp = KQMLPerformative('SUCCESS')
        resp.set('status', 'FINISHED')
        resp.set('entities-found',
                 self.make_cljson(agents) if agents else KQMLList([]))
        resp.set('num-relations-found', str(len(stmts)))
        resp.set('dump-limit', str(DUMP_LIMIT))
        resp.sets('suggestion', description if description else 'nil')
        top_stmts = self.make_cljson(stmts[:10]) if stmts else KQMLList([])
        resp.set('top-stmts', top_stmts)
        return resp

    def respond_confirm_relation_from_literature(self, content):
        """Confirm a protein-protein interaction given subject, object, verb"""
        try:
            subj, obj, stmt_type, filter_agents, context_agents = \
                self._get_query_info(content)
            finder = \
                self.msa.find_mechanism_from_input(subj, obj, None, stmt_type,
                                                   ev_limit=5, persist=False,
                                                   timeout=5,
                                                   filter_agents=filter_agents,
                                                   context_agents=context_agents)
            self._send_provenance_async(finder,
                'confirming that some statements match')
        except MSALookupError as mle:
            return self.make_failure(mle.args[0])
        stmts = finder.get_statements(timeout=20)
        if stmts is None:
            # TODO: Handle this more gracefully, if possible.
            return self.make_failure('MISSING_MECHANISM')
        num_stmts = len(stmts)
        description = finder.describe(include_negative=False) \
            if stmts else None
        #self.say(description)
        resp = KQMLPerformative('SUCCESS')
        resp.set('some-relations-found', 'TRUE' if num_stmts else 'FALSE')
        resp.set('num-relations-found', str(num_stmts))
        resp.set('dump-limit', str(DUMP_LIMIT))
        resp.sets('suggestion', description if description else 'nil')
        return resp

    def respond_get_paper_model(self, content):
        """Get and display the model from a paper, indicated by pmid."""
        pmid_raw = content.gets('pmid')
        prefix = 'PMID-'
        if pmid_raw.startswith(prefix) and pmid_raw[len(prefix):].isdigit():
            pmid = pmid_raw[len(prefix):]
        else:
            return self.make_failure('BAD_INPUT')
        try:
            p = get_statements_for_paper([('pmid', pmid)])
            stmts = p.statements
        except IndraDBRestAPIError as e:
            if e.status_code == 404 and 'Invalid or unavailable' in e.reason:
                logger.error("Could not find pmid: %s" % e.reason)
                return self.make_failure('MISSING_MECHANISM')
            else:
                raise e

        if not stmts:
            resp = KQMLPerformative('SUCCESS')
            resp.set('relations-found', 0)
            return resp
        stmts = ac.map_grounding(stmts)
        stmts = ac.map_sequence(stmts)
        unique_stmts = ac.run_preassembly(stmts, return_toplevel=True)
        diagrams = _make_diagrams(stmts)
        self.send_display_model(diagrams)
        resp = KQMLPerformative('SUCCESS')
        resp.set('relations-found', len(unique_stmts))
        resp.set('dump-limit', str(DUMP_LIMIT))
        return resp

    def send_display_model(self, diagrams):
        for diagram_type, resource in diagrams.items():
            if not resource:
                continue
            if diagram_type == 'sbgn':
                content = KQMLList('display-sbgn')
                content.set('type', diagram_type)
                content.sets('graph', resource)
            else:
                content = KQMLList('display-image')
                content.set('type', diagram_type)
                content.sets('path', resource)
            self.tell(content)

    def _send_display_stmts(self, finder, nl_question):
        try:
            logger.debug("Waiting for statements to finish...")
            stmts = finder.get_statements(block=True)
            if stmts is None:
                return
            start_time = datetime.now()
            logger.info('Sending display statements.')
            self.send_provenance_for_stmts(stmts, nl_question,
                ev_counts=finder.get_ev_totals(),
                source_counts=finder.get_source_counts())
            logger.info("Finished sending provenance after %s seconds."
                        % (datetime.now() - start_time).total_seconds())
        except Exception as e:
            logger.exception(e)
            logger.error("Failed to post provenance.")
            raise


def _make_sbgn(stmts):
    sa = SBGNAssembler()
    sa.add_statements(stmts)
    sa.make_model()
    sbgn_str = sa.print_model()
    logger.info(sbgn_str)
    return sbgn_str


def _make_diagrams(stmts):
    sbgn = _make_sbgn(stmts)
    diagrams = {'sbgn': sbgn.decode('utf-8')}
    return diagrams


def _get_agent_if_present(content, key):
    obj_clj = content.get(key)
    if obj_clj is None:
        return None
    else:
        agent = Bioagent.get_agent(obj_clj)
        # This is a bug in the BA that we can handle here
        if isinstance(agent, list):
            agent = agent[0]
        return agent


if __name__ == "__main__":
    MSA_Module(argv=sys.argv[1:])
