import os
import sys
import logging
import indra
from indra.util import read_unicode_csv
from indra.tools import expand_families, assemble_corpus
from indra.sources import trips
from bioagents import Bioagent
from indra.databases import get_identifiers_url
from indra.preassembler.hierarchy_manager import hierarchies
from indra.sources.trips.processor import TripsProcessor
from kqml import KQMLModule, KQMLPerformative, KQMLList, KQMLString


logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('MSA')


def _read_signor_afs():
    path = os.path.dirname(os.path.abspath(__file__)) + \
            '/../resources/signor_active_forms.pkl'
    signor_afs = assemble_corpus.load_statements(path)
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
        target_ekb = content.gets('target')
        if target_ekb is None or target_ekb == '':
            return self.make_failure('MISSING_TARGET')
        agent = self._get_agent(target_ekb)
        logger.debug('Found agent (target): %s.' % agent.name)
        residue = content.gets('residue')
        position = content.gets('position')
        related_results = [
            s for s in self.signor_afs
            if self._matching(s, agent, residue, position)
            ]
        if not len(related_results):
            return self.make_failure('MISSING_MECHANISM',
                "Could not find statement matching phosphorylation activating "
                "%s, %s, %s." % (agent.name, residue, position)
                )
        msg = KQMLPerformative('SUCCESS')
        msg.set('is-activating', 'TRUE')
        return msg

    @staticmethod
    def _get_agent(agent_ekb):
        tp = TripsProcessor(agent_ekb)
        terms = tp.tree.findall('TERM')
        term_id = terms[0].attrib['id']
        agent = tp._get_agent_by_id(term_id, None)
        return agent

    def _matching(self, stmt, agent, residue, position):
        return (
            stmt.agent.name == agent.name
            and any([
                (m.residue == residue and m.position == position)
                for m in stmt.agent.mods
                ]))


if __name__ == "__main__":
    MSA_Module(argv=sys.argv[1:])
