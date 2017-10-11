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
        target = content.gets('target')
        residue = content.gets('residue')
        position = content.gets('position')
        msg = KQMLPerformative('SUCCESS')
        msg.set('is-activating', 'TRUE')
        return msg


if __name__ == "__main__":
    MSA_Module(argv=sys.argv[1:])
