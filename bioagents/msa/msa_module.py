import os
import sys
import re
import pickle
import logging
from datetime import datetime
from threading import Thread

from indra.statements import Agent

logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('MSA-module')

from kqml import KQMLPerformative, KQMLList

from indra import has_config
from indra.sources.trips.processor import TripsProcessor
from indra.assemblers.sbgn import SBGNAssembler
from indra.tools import assemble_corpus as ac

from bioagents.msa.msa import MSA
from bioagents import Bioagent

if has_config('INDRA_DB_REST_URL') and has_config('INDRA_DB_REST_API_KEY'):
    from indra.sources.indra_db_rest import get_statements, IndraDBRestAPIError, \
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

    def __init__(self):
        self.msa = MSA()
        return

    def respond_get_common(self, content):
        """Find the common up/down streams of a protein."""
        # TODO: This entire function could be part of the MSA.
        if not CAN_CHECK_STATEMENTS:
            return self.make_failure(
                'NO_KNOWLEDGE_ACCESS',
                'Cannot access the database through the web api.'
                )
        genes_ekb = content.gets('genes')
        agents = _get_agents(genes_ekb)
        if len(agents) < 2:
            return self.make_failure('NO_TARGET',
                                     'Only %d < 2 agents given.' % len(agents))

        direction = content.gets('up-down')
        logger.info("Got genes: %s and direction %s." % (agents, direction))

        # Choose some parameters based on direction.
        if direction == 'ONT::PREDECESSOR':
            meth = 'FromTarget'
            other_idx = 0
            prefix = 'up'
        elif direction == 'ONT::SUCCESSOR':
            meth = 'FromSubject'
            other_idx = 1
            prefix = 'down'
        else:
            # TODO: With the new MSA we could handle common neighbors.
            return self.make_failure("UNKNOWN_ACTION", direction)

        # Find the commonalities.
        commons = {}
        first = True
        for ag in agents:

            # Look for HGNC or FPLX, and fail if neither is found.
            for ns in ['HGNC', 'FPLX']:
                dbid = ag.db_refs.get(ns)
                if dbid:
                    break
            else:
                return self.make_failure('MISSING_TARGET',
                                         'Agent lacks both HGNC and FPLX ids.')

            # Look for statements for this agent.
            finder = self.msa.find_mechanisms(meth, ag, ev_limit=2,
                                              persist=False, max_stmts=100)

            # TODO: much of this work could be offloaded into the MSA.
            # Look for matches with existing up- or down-streams.
            for stmt in finder.get_statements():
                other_ag = stmt.agent_list()[other_idx]
                if other_ag is None or 'HGNC' not in other_ag.db_refs.keys():
                    continue
                other_id = other_ag.name
                if first and other_id not in commons.keys():
                    commons[other_id] = {dbid: [stmt]}
                elif other_id in commons.keys():
                    if dbid not in commons[other_id].keys():
                        commons[other_id][dbid] = []
                    commons[other_id][dbid].append(stmt)

            # Remove all entries that didn't find match this time around.
            if not first:
                commons = {other_id: data for other_id, data in commons.items()
                           if dbid in data.keys()}

            # Check for the empty condition
            if not commons:
                break

            # The next run is definitely not the first.
            first = False

        # Get post statements to provenance.
        stmts = [s for data in commons.values() for s_list in data.values()
                 for s in s_list]
        if len(agents) > 2:
            name_list = ', '.join(ag.name for ag in agents[:-1]) + ','
        else:
            name_list = agents[0].name
        name_list += ' and ' + agents[-1].name
        msg = ('%sstreams of ' % prefix).capitalize() + name_list
        self.send_provenance_for_stmts(stmts, msg)

        # Create the reply
        resp = KQMLPerformative('SUCCESS')
        gene_list = KQMLList()
        for ag_name in commons.keys():
            gene_list.append(ag_name)
        resp.set('commons', gene_list)
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
        m = re.match('(\w+)-(\w+)', heading)
        if m is None:
            return self.make_failure('UNKNOWN_ACTION')
        action, polarity = [s.lower() for s in m.groups()]
        target_ekb = content.gets('target')
        if target_ekb is None or target_ekb == '':
            return self.make_failure('MISSING_TARGET')
        agent = _get_agent(target_ekb)
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

        finder = self.msa.find_phos_activeforms(agent)
        self.say(finder.describe())

        related_result_dict = {}
        stmts = finder.get_statements()
        for s in stmts:
            if self._matching(s, residue, position, action, polarity):
                related_result_dict[s.matches_key()] = s

        logger.info("Found %d matching statements." % len(related_result_dict))
        if not len(related_result_dict):
            return self.make_failure(
                'MISSING_MECHANISM',
                "Could not find statement matching phosphorylation activating "
                "%s, %s, %s, %s." % (agent.name, residue, position,
                                     'phosphorylation')
                )
        else:
            self.send_provenance_for_stmts(
                related_result_dict.values(),
                "Phosphorylation at %s%s activates %s." % (
                    residue,
                    position,
                    agent.name
                    )
                )
            msg = KQMLPerformative('SUCCESS')
            msg.set('is-activating', 'TRUE')
            return msg

    def _make_nl_description(self, verb, subj, obj):
        """Make a human-readable description of a query."""
        question_input = {k: ag.name if ag else 'unknown'
                          for k, ag in [('subject', subj), ('object', obj)]}
        question_input['stmt_type'] = verb
        fmt = ('subject: {subject}, statement type: {stmt_type}, '
               'object: {object}')
        ret = fmt.format(**question_input)
        return ret

    def _lookup_from_source_type_target(self, content, desc, timeout=20,
                                        send_provenance=True):
        """Look up statement given info received by find/confirm relations."""
        start_time = datetime.now()
        subj = _get_agent(content.gets('source'))
        obj = _get_agent(content.gets('target'))
        stmt_type = content.gets('type')
        if stmt_type == 'unknown':
            stmt_type = None
        nl = self._make_nl_description(stmt_type, subj, obj)
        nl = "%s: %s" % (desc, nl)
        logger.info("Got a query for %s." % nl)

        # Try to get related statements.
        finder = self.msa.find_mechanism_from_input(subj, obj, None, stmt_type,
                                                    ev_limit=3, persist=False,
                                                    timeout=timeout)
        num_stmts = len(finder.get_statements(block=False))
        logger.info("Retrieved %d statements after %s seconds."
                    % (num_stmts, (datetime.now()-start_time).total_seconds()))
        if send_provenance:
            try:
                th = Thread(target=self._send_display_stmts, args=(finder, nl))
                th.start()
            except Exception as e:
                logger.warning("Failed to start thread to send provenance.")
                logger.exception(e)

        return finder

    def respond_find_relations_from_literature(self, content):
        """Find statements matching some subject, verb, object information."""
        try:
            finder = self._lookup_from_source_type_target(content, 'Find',
                                                          timeout=5)
        except MSALookupError as mle:
            return self.make_failure(mle.args[0])

        stmts = finder.get_statements(timeout=15)
        if stmts is None:
            # Calling this success may be a bit ambitious.
            resp = KQMLPerformative('SUCCESS')
            resp.set('status', 'WORKING')
            resp.set('relations-found', 'nil')
            resp.set('dump-limit', str(DUMP_LIMIT))
            return resp

        self.say(finder.describe())
        resp = KQMLPerformative('SUCCESS')
        resp.set('status', 'FINISHED')
        resp.set('relations-found', str(len(stmts)))
        resp.set('dump-limit', str(DUMP_LIMIT))
        return resp

    def respond_confirm_relation_from_literature(self, content):
        """Confirm a protein-protein interaction given subject, object, verb"""
        try:
            finder = self._lookup_from_source_type_target(content, 'Confirm')
        except MSALookupError as mle:
            return self.make_failure(mle.args[0])
        stmts = finder.get_statements(timeout=20)
        if stmts is None:
            # TODO: Handle this more gracefully, if possible.
            return self.make_failure('MISSING_MECHANISM')
        num_stmts = len(stmts)
        self.say(finder.describe())
        resp = KQMLPerformative('SUCCESS')
        resp.set('some-relations-found', 'TRUE' if num_stmts else 'FALSE')
        resp.set('num-relations-found', str(num_stmts))
        resp.set('dump-limit', str(DUMP_LIMIT))
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
            stmts = get_statements_for_paper([('pmid', pmid)])
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

    def _send_display_stmts(self, resp, nl_question):
        try:
            logger.debug("Waiting for statements to finish...")
            resp.wait_until_done()
            if not len(resp.statements):
                return
            start_time = datetime.now()
            logger.info('Sending display statements.')
            self.send_provenance_for_stmts(resp.statements, nl_question)
            logger.info("Finished sending provenance after %s seconds."
                        % (datetime.now() - start_time).total_seconds())
        except Exception as e:
            logger.exception(e)
            logger.error("Failed to post provenance.")
            raise

    def _format_evidence(self, ev_list, ev_count):
        """Format the evidence of a statement for display."""
        fmt = ('{source_api}: <a href=https://www.ncbi.nlm.nih.gov/pubmed/'
               '{pmid} target="_blank">{pmid}</a>')
        pmids = [fmt.format(**ev.__dict__) for ev in ev_list[:10]]
        if len(pmids) < ev_count:
            pmids.append('...and %d more!' % (ev_count - len(pmids)))
        return ', '.join(pmids)

    def _send_table_to_provenance(self, resp, nl_question):
        """Post a concise table listing statements found."""
        html_str = '<h4>Statements matching: %s</h4>\n' % nl_question
        html_str += '<table style="width:100%">\n'
        row_list = ['<th>Source</th><th>Interactions</th><th>Target</th>'
                    '<th>Source and PMID</th>']
        logger.info("Sending %d statements to provenance."
                    % min(len(resp.statements), DUMP_LIMIT))
        print("Generating html: ", end='', flush=True)
        for i, stmt in enumerate(resp.statements[:DUMP_LIMIT]):
            if i % 5 == 0:
                print('|', end='', flush=True)
            sub_ag, obj_ag = stmt.agent_list()
            ev_str = self._format_evidence(stmt.evidence,
                                           resp.get_ev_count(stmt))
            row_list.append('<td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
                            % (sub_ag, type(stmt).__name__, obj_ag, ev_str))
        html_str += '\n'.join(['  <tr>%s</tr>\n' % row_str
                               for row_str in row_list])
        html_str += '</table>'
        print(" DONE...", end='', flush=True)
        content = KQMLList('add-provenance')
        content.sets('html', html_str)
        print("SENT!")
        return self.tell(content)

    def _matching(self, stmt, residue, position, action, polarity):
        if stmt.is_active is not (polarity == 'activating'):
            return False
        matching_residues = any([
            m.residue == residue
            and m.position == position
            and m.mod_type == action
            for m in stmt.agent.mods])
        return matching_residues


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


def _get_agent(agent_ekb):
    try:
        agents = _get_agents(agent_ekb)
    except Exception as e:
        logger.error("Got exception while converting ekb in an agent:\n"
                     "%s" % agent_ekb)
        logger.exception(e)
        raise MSALookupError('MISSING_TARGET')
    agent = None
    if len(agents):
        agent = agents[0]
    return agent


def _get_agents(ekb):
    tp = TripsProcessor(ekb)
    terms = tp.tree.findall('TERM')
    results = [tp._get_agent_by_id(t.attrib['id'], None) for t in terms]
    return [ag for ag in results if isinstance(ag, Agent)]


if __name__ == "__main__":
    MSA_Module(argv=sys.argv[1:])
