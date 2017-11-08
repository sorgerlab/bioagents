import os
import sys
import logging
import re
from bioagents import Bioagent
from indra.sources.trips.processor import TripsProcessor
from kqml import KQMLPerformative, KQMLList
import pickle
from indra.assemblers.english_assembler import EnglishAssembler


logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('MSA')


def _read_signor_afs():
    path = os.path.dirname(os.path.abspath(__file__)) + \
            '/../resources/signor_active_forms.pkl'
    with open(path, 'rb') as pkl_file:
        stmts = pickle.load(pkl_file)
    if isinstance(stmts, dict):
        signor_afs = []
        for _, stmt_list in stmts.iteritems():
            signor_afs += stmt_list
    else:
        signor_afs = stmts
    return signor_afs


class MSA_Module(Bioagent):
    name = 'MSA'
    tasks = ['PHOSPHORYLATION-ACTIVATING']
    signor_afs = _read_signor_afs()

    def receive_tell(self, msg, content):
        tell_content = content[0].to_string().upper()
        if tell_content == 'START-CONVERSATION':
            logger.info('MSA resetting')

    def respond_phosphorylation_activating(self, content):
        """Return response content to phosphorylation_activating request."""
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
        residue = content.gets('residue')
        position = content.gets('position')
        related_results = [
            s for s in self.signor_afs
            if self._matching(s, agent, residue, position, action, polarity)
            ]
        if not len(related_results):
            return self.make_failure(
                'MISSING_MECHANISM',
                "Could not find statement matching phosphorylation activating "
                "%s, %s, %s, %s." % (agent.name, residue, position, 'phosphorylation')
                )
        else:
            self._add_provenance_for_stmts(
                related_results,
                "Phosphorylation at %s%s activates %s." % (
                    residue,
                    position,
                    agent.name
                    )
                )
            msg = KQMLPerformative('SUCCESS')
            msg.set('is-activating', 'TRUE')
            return msg

    def _add_provenance_for_stmts(self, stmt_list, for_what, with_stmt=False):
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
            return '%s: ' % EnglishAssembler([stmt]).make_model()

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

    @staticmethod
    def _get_agent(agent_ekb):
        tp = TripsProcessor(agent_ekb)
        terms = tp.tree.findall('TERM')
        term_id = terms[0].attrib['id']
        agent = tp._get_agent_by_id(term_id, None)
        return agent

    def _matching(self, stmt, agent, residue, position, action, polarity):
        if stmt.agent.name != agent.name:
            return False
        if stmt.is_active is not (polarity == 'activating'):
            return False
        matching_residues = any([
            m.residue == residue
            and m.position == position
            and m.mod_type == action
            for m in stmt.agent.mods])
        return matching_residues


if __name__ == "__main__":
    MSA_Module(argv=sys.argv[1:])
