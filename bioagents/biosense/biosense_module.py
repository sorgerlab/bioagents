import sys
import logging
import indra
from indra.databases import uniprot_client, get_identifiers_url
from bioagents import Bioagent, add_agent_type
from kqml import  KQMLString
from .biosense import BioSense
from .biosense import UnknownCategoryError, SynonymsUnknownError
from .biosense import CollectionNotFamilyOrComplexError
from kqml import KQMLPerformative, KQMLList
from bioagents.ekb import KQMLGraph, EKB


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
        else:
            id_base = id

        context = content.get('context').to_string()
        # First get the KQML graph object for the given context
        graph = KQMLGraph(context)

        try:
            # Then turn the graph into an EKB XML object, expanding around the
            # given ID
            ekb = EKB(graph, id_base)
            entity = ekb.get_entity()
            js = self.make_cljson(entity)
        except Exception as e:
            logger.info("Encountered an error while parsing: %s. "
                        "Returning empty list." % content.to_string())
            logger.exception(e)
            js = KQMLList()
        msg = KQMLPerformative('done')
        msg.sets('result', js)
        return msg

    def respond_choose_sense(self, content):
        """Return response content to choose-sense request."""
        agent_clj = content.get('agent')
        agent = self.get_agent(agent_clj)
        if not agent:
            return self.make_failure('MISSING_AGENT')
        add_agent_type(agent)

        def _get_urls(agent):
            urls = {k: get_identifiers_url(k, v) for k, v in
                    agent.db_refs.items()
                    if k not in {'TEXT', 'TYPE', 'TRIPS'}}
            return urls

        msg = KQMLPerformative('SUCCESS')
        msg.set('agent', self.make_cljson(agent))

        description = None
        if 'UP' in agent.db_refs:
            description = uniprot_client.get_function(agent.db_refs['UP'])
        if description:
            msg.sets('description', description)

        urls = _get_urls(agent)
        if urls:
            url_parts = [KQMLList([':name', KQMLString(k),
                                   ':dblink', KQMLString(v)])
                         for k, v in urls.items()]
            url_list = KQMLList()
            for url_part in url_parts:
                url_list.append(url_part)
            msg.set('id-urls', url_list)

        return msg

    def respond_choose_sense_category(self, content):
        """Return response content to choose-sense-category request."""
        term_arg = content.get('ekb-term')
        term_agent = self.get_agent(term_arg)
        if term_agent is None:
            return self.make_failure('INVALID_AGENT')
        category = content.gets('category')
        try:
            in_category = self.bs.choose_sense_category(term_agent, category)
        except UnknownCategoryError:
            return self.make_failure('UNKNOWN_CATEGORY')
        msg = KQMLList('SUCCESS')
        msg.set('in-category', 'TRUE' if in_category else 'FALSE')
        return msg

    def respond_choose_sense_is_member(self, content):
        """Return response content to choose-sense-is-member request."""
        agent_arg = content.get('ekb-term')
        agent = self.get_agent(agent_arg)
        if agent is None:
            return self.make_failure('INVALID_AGENT')
        collection_arg = content.get('collection')
        collection = self.get_agent(collection_arg)
        if collection is None:
            return self.make_failure('INVALID_COLLECTION')
        try:
            is_member = self.bs.choose_sense_is_member(agent, collection)
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
        if collection is None:
            return self.make_failure('INVALID_COLLECTION')
        try:
            members = self.bs.choose_sense_what_member(collection)
        except CollectionNotFamilyOrComplexError:
            return self.make_failure('COLLECTION_NOT_FAMILY_OR_COMPLEX')
        msg = KQMLList('SUCCESS')
        msg.set('members', self.make_cljson(members))
        return msg

    def respond_get_synonyms(self, content):
        """Respond to a query looking for synonyms of a protein."""
        entity_arg = content.get('entity')
        entity = self.get_agent(entity_arg)
        if entity is None:
            return self.make_failure('INVALID_AGENT')
        try:
            synonyms = self.bs.get_synonyms(entity)
        except SynonymsUnknownError:
            return self.make_failure('SYNONYMS_UNKNOWN')
        else:
            syns_kqml = KQMLList()
            for s in synonyms:
                entry = KQMLList()
                entry.sets(':name', s)
                syns_kqml.append(entry)
            msg = KQMLList('SUCCESS')
            msg.set('synonyms', syns_kqml)
        return msg


if __name__ == "__main__":
    BioSense_Module(argv=sys.argv[1:])
