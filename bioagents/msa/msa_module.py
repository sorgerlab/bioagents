import os
import sys
import re
import pickle
import logging
from itertools import groupby

logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('MSA')

from kqml import KQMLPerformative, KQMLList

from indra import has_config
from indra.sources.trips.processor import TripsProcessor
from indra.assemblers import SBGNAssembler
from indra.tools import assemble_corpus as ac

if has_config('INDRA_DB_REST_URL') and has_config('INDRA_DB_REST_API_KEY'):
    from indra.sources.indra_db_rest import get_statements, IndraDBRestError, \
                                            get_statements_for_paper

    CAN_CHECK_STATEMENTS = True
else:
    logger.warning("Database web api not specified. Cannot get background.")
    CAN_CHECK_STATEMENTS = False

from bioagents import Bioagent


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


DUMP_LIMIT = 20


class MSALookupError(Exception):
    pass


class MSA_Module(Bioagent):
    name = 'MSA'
    tasks = ['PHOSPHORYLATION-ACTIVATING', 'FIND-RELATIONS-FROM-LITERATURE',
             'GET-PAPER-MODEL', 'CONFIRM-RELATION-FROM-LITERATURE']
    signor_afs = _read_signor_afs()

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
        agent = self._get_agent(target_ekb)
        logger.debug('Found agent (target): %s.' % agent.name)
        site = content.gets('site')
        residue, position = site.split('-')
        related_result_dict = {}
        logger.info("Looking for statements with agent %s of type %s."
                    % (str(agent), 'ActiveForm'))
        for namespace, name in agent.db_refs.items():
            # TODO: Remove this eventually, as it is a temporary work-around.
            if namespace == 'FPLX':
                namespace = 'BE'
            logger.info("Checking namespace: %s" % namespace)
            stmts = get_statements(agents=['%s@%s' % (name, namespace)],
                                   stmt_type='ActiveForm')
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

    def _make_nl_description(self, subject='unknown', object='unknown',
                             stmt_type='unkown'):
        """Make a human-readable description of a query."""
        fmt = ('subject: {subject}, statement type: {stmt_type}, '
               'object: {object}')
        ret = fmt.format(subject=subject, object=object, stmt_type=stmt_type)
        return ret

    def _lookup_from_source_type_target(self, content, desc):
        """Look up statement given format received by find/confirm relations."""
        agent_dict = dict.fromkeys(['subject', 'object'])
        for pos, loc in [('subject', 'source'), ('object', 'target')]:
            ekb = content.gets(loc)
            try:
                agent = self._get_agent(ekb)
                if agent is None:
                    agent_dict[pos] = None
                else:
                    agent_dict[pos] = {'name': agent.name}
                    agent_dict[pos].update(agent.db_refs)
            except Exception as e:
                logger.error("Got exception while converting ekb for %s "
                             "(%s) into an agent." % (pos, ekb))
                logger.exception(e)
                raise MSALookupError('MISSING_TARGET')
        stmt_type = content.gets('type')
        if stmt_type == 'unknown':
            stmt_type = None
        question_input = {k: v['name'] if v else 'unknown'
                          for k, v in agent_dict.items()}
        nl = self._make_nl_description(stmt_type=stmt_type, **question_input)
        nl = "%s: %s" % (desc, nl)
        logger.info("Got a query for %s." % nl)
        # Try to get related statements.
        try:
            input_dict = {'stmt_type': stmt_type}

            # Use the best available db ref for each agent.
            for pos, ref_dict in agent_dict.items():
                if ref_dict is None:
                    input_dict[pos] = None
                else:
                    for key in ['HGNC', 'FPLX', 'CHEBI', 'TEXT']:
                        if key in ref_dict.keys():
                            if key == 'FPLX':
                                flag = 'BE'
                            else:
                                flag = key
                            inp = r'%s@%s' % (ref_dict[key], flag)
                            input_dict[pos] = inp
                            break

            # Actually get the statements.
            stmts = get_statements(**input_dict)
            logger.info("Found %d stmts" % len(stmts))
        except IndraDBRestError as e:
            logger.error("Failed to get statements.")
            logger.exception(e)
            raise MSALookupError('MISSING_MECHANISM')

        # Sort statements by support and evidence
        stmts.sort(key=lambda s: len(s.evidence) + len(s.supported_by))

        return nl, stmts

    def respond_find_relations_from_literature(self, content):
        """Find statements matching some subject, verb, object information."""
        try:
            nl_question, stmts =\
                self._lookup_from_source_type_target(content, 'Find')
        except MSALookupError as mle:
            return self.make_failure(mle.args[0])

        # For now just list the statements in the provenance tab. Only captures
        # the top 5.
        try:
            self._send_display_stmts(stmts, nl_question)
        except Exception as e:
            logger.warning("Failed to send provenance.")
            logger.exception(e)

        # Assuming we haven't hit any errors yet, return SUCCESS
        resp = KQMLPerformative('SUCCESS')
        resp.set('relations-found', str(len(stmts)))
        resp.set('dump-limit', str(DUMP_LIMIT))
        return resp

    def respond_confirm_relation_from_literature(self, content):
        """Confirm a protein-protein interaction given subject, object, verb."""
        try:
            nl_question, stmts = \
                self._lookup_from_source_type_target(content, 'Confirm')
        except MSALookupError as mle:
            return self.make_failure(mle.args[0])
        if len(stmts):
            self._send_display_stmts(stmts, nl_question)
        resp = KQMLPerformative('SUCCESS')
        resp.set('some-relations-found', 'TRUE' if len(stmts) > 0 else 'FALSE')
        resp.set('num-relations-found', str(len(stmts)))
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
            stmts = get_statements_for_paper(pmid, id_type='pmid')
        except IndraDBRestError as e:
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

    def _send_display_stmts(self, stmts, nl_question):
        logger.info('Sending display statements')
        display_stmts = []
        for stmt_type, stmt_grp in groupby(stmts, key=lambda s: str(type(s))):
            stmt_sublist = list(stmt_grp)
            logger.info("There are %d statements of type %s."
                        % (len(stmt_sublist), stmt_type))
            stmt_sublist.sort(key=lambda s: len(s.evidence)+len(s.supported_by))
            display_stmts.extend(stmt_sublist[:DUMP_LIMIT])
        self._send_table_to_provenance(display_stmts, nl_question)
        # resource = _make_sbgn(stmts[:10])
        # logger.info(resource)
        # content = KQMLList('open-query-window')
        # content.sets('cyld', '#1')
        # content.sets('graph', resource)
        # self.tell(content)

    def _send_table_to_provenance(self, stmts, nl_question):
        """Post a concise table listing statements found."""
        html_str = '<h4>Statements matching: %s</h4>\n' % nl_question
        html_str += '<table style="width:100%">\n'
        row_list = ['<th>Source</th><th>Interactions</th><th>Target</th>']
        for stmt in stmts[:DUMP_LIMIT]:
            sub_ag, obj_ag = stmt.agent_list()
            row_list.append('<td>%s</td><td>%s</td><td>%s</td>'
                            % (sub_ag, type(stmt).__name__, obj_ag))
        html_str += '\n'.join(['  <tr>%s</tr>\n' % row_str
                               for row_str in row_list])
        html_str += '</table>'
        content = KQMLList('add-provenance')
        content.sets('html', html_str)
        return self.tell(content)

    @staticmethod
    def _get_agent(agent_ekb):
        tp = TripsProcessor(agent_ekb)
        terms = tp.tree.findall('TERM')
        if len(terms):
            term_id = terms[0].attrib['id']
            agent = tp._get_agent_by_id(term_id, None)
        else:
            agent = None
        return agent

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


if __name__ == "__main__":
    MSA_Module(argv=sys.argv[1:])
