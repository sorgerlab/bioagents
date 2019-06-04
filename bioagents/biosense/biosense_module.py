import sys
import logging
import indra
from indra.sources import trips
from .biosense import BioSense
from .biosense import InvalidAgentError, UnknownCategoryError, \
    SynonymsUnknownError
from .biosense import InvalidCollectionError, CollectionNotFamilyOrComplexError
from bioagents import Bioagent, add_agent_type
from kqml import KQMLPerformative, KQMLList
from bioagents.ekb import KQMLGraph, EKB, agent_from_term


logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('BIOSENSE')


_indra_path = indra.__path__[0]


class BioSense_Module(Bioagent):
    def __init__(self, **kwargs):
        # Instantiate a singleton BioSense agent
        self.bs = BioSense()
        super(BioSense_Module, self).__init__(**kwargs)

    name = 'BioSense'
    tasks = ['CHOOSE-SENSE', 'CHOOSE-SENSE-CATEGORY',
             'CHOOSE-SENSE-IS-MEMBER', 'CHOOSE-SENSE-WHAT-MEMBER',
             'GET-SYNONYMS', 'GET-INDRA-REPRESENTATION']

    def respond_get_indra_representation(self, content):
        """Return the INDRA CL-JSON corresponding to the given content."""
        id = content.get('ids')[0].to_string()
        if id.startswith('ONT::'):
            id_base = id[5:]
        context = content.get('context').to_string()
        # First get the KQML graph object for the given context
        graph = KQMLGraph(context)
        # Then turn the graph into an EKB XML object, expanding around the
        # given ID
        ekb = EKB(graph, id_base)
        # Now process the EKB using the TRIPS processor to extract Statements
        tp = trips.process_xml(ekb.to_string())
        # If there are any statements then we can return the CL-JSON of those
        if tp.statements:
            js = self.make_cljson(tp.statements)
        # Otherwise, we try extracting an Agent and return that
        else:
            try:
                agent = agent_from_term(graph, id_base)
                # Set the TRIPS ID in db_refs
                agent.db_refs['TRIPS'] = id
                # Infer the type from db_refs
                agent = add_agent_type(agent)
                js = self.make_cljson(agent)
            except Exception as e:
                logger.info("Encountered an error while parsing: %s."
                            "Returning empty list." % content.to_string())
                logger.exception(e)
                js = KQMLList()
        msg = KQMLPerformative('done')
        msg.sets('result', js)
        return msg

    def respond_choose_sense(self, content):
        """Return response content to choose-sense request."""
        term_arg = content.get('ekb-term')
        term_agent = self.get_agent(term_arg)
        msg = KQMLPerformative('SUCCESS')
        agent_clj = self.make_cljson(term_agent)
        msg.set('agents', agent_clj)
        return msg

    def respond_choose_sense_category(self, content):
        """Return response content to choose-sense-category request."""
        term_arg = content.get('ekb-term')
        term_agent = self.get_agent(term_arg)
        category = content.gets('category')
        try:
            in_category = self.bs.choose_sense_category(term_agent, category)
        except InvalidAgentError:
            msg = make_failure('INVALID_AGENT')
        except UnknownCategoryError:
            msg = make_failure('UNKNOWN_CATEGORY')
        else:
            msg = KQMLList('SUCCESS')
            msg.set('in-category', 'TRUE' if in_category else 'FALSE')
        return msg

    def respond_choose_sense_is_member(self, content):
        """Return response content to choose-sense-is-member request."""
        agent_arg = content.get('ekb-term')
        agent = self.get_agent(agent_arg)
        collection_arg = content.get('collection')
        collection = self.get_agent(collection_arg)
        try:
            is_member = self.bs.choose_sense_is_member(agent, collection)
        except InvalidAgentError:
            msg = make_failure('INVALID_AGENT')
        except InvalidCollectionError:
            msg = make_failure('INVALID_COLLECTION')
        except CollectionNotFamilyOrComplexError:
            msg = KQMLList('SUCCESS')
            msg.set('is-member', 'FALSE')
        else:
            msg = KQMLList('SUCCESS')
            msg.set('is-member', 'TRUE' if is_member else 'FALSE')
        return msg

    def respond_choose_sense_what_member(self, content):
        """Return response content to choose-sense-what-member request."""
        # Get the collection agent
        collection_arg = content.get('collection')
        collection = self.get_agent(collection_arg)
        try:
            members = self.bs.choose_sense_what_member(collection)
        except InvalidCollectionError:
            msg = make_failure('INVALID_COLLECTION')
        except CollectionNotFamilyOrComplexError:
            msg = make_failure('COLLECTION_NOT_FAMILY_OR_COMPLEX')
        else:
            msg = KQMLList('SUCCESS')
            msg.set('members', self.make_cljson(members))
        return msg

    def respond_get_synonyms(self, content):
        """Respond to a query looking for synonyms of a protein."""
        entity_arg = content.get('entity')
        entity = self.get_agent(entity_arg)
        try:
            synonyms = self.bs.get_synonyms(entity)
        except InvalidAgentError:
            msg = self.make_failure('INVALID_AGENT')
        except SynonymsUnknownError:
            msg = self.make_failure('SYNONYMS_UNKNOWN')
        else:
            syns_kqml = KQMLList()
            for s in synonyms:
                entry = KQMLList()
                entry.sets(':name', s)
                syns_kqml.append(entry)
            msg = KQMLList('SUCCESS')
            msg.set('synonyms', syns_kqml)
        return msg


def make_failure(reason):
    msg = KQMLList('FAILURE')
    msg.set('reason', reason)
    return msg


if __name__ == "__main__":
    BioSense_Module(argv=sys.argv[1:])
