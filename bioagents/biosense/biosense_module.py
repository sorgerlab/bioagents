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
        # First get the KQML graph object for the given context
        context = content.get('context').to_string()
        graph = KQMLGraph(context)

        ekbs = []
        for trips_id_obj in content.get('ids'):
            trips_id = trips_id_obj.to_string()
            if trips_id.startswith('ONT::'):
                trips_id = trips_id[5:]

            try:
                # Turn the graph into an EKB XML object, expanding around
                # the given ID.
                ekb = EKB(graph, trips_id)
                logger.debug('Extracted EKB: %s' % ekb.to_string())
                ekbs.append((trips_id, ekb))
            except Exception as e:
                logger.error('Encountered an error while parsing: %s.' %
                             content.to_string())
                logger.exception(e)

        msg = KQMLPerformative('done')
        if not ekbs:
            msg.set('result', KQMLList())
            return msg
        elif len(ekbs) == 1:
            ekbs_to_extract = ekbs
        else:
            ekbs_to_extract = []
            for idx, (trips_id, ekb) in enumerate(ekbs):
                other_ekbs = ekbs[:idx] + ekbs[idx+1:]
                other_components = set.union(*[set(e.components)
                                               for _, e in other_ekbs])
                if trips_id in other_components:
                    continue
                ekbs_to_extract.append((trips_id, ekb))

        entities = KQMLList()
        for trips_id, ekb in ekbs_to_extract:
            entity = ekb.get_entity()
            if entity is None:
                logger.info("Could not resolve entity from: %s. " %
                            ekb.to_string())
            else:
                js = self.make_cljson(entity)
                entities.append(js)

        if len(entities) == 1:
            msg.sets('result', entities[0])
        else:
            msg.set('result', entities)
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
