import logging
from indra import __path__ as _indra_path
from indra.sources import trips
from indra.sources.trips.processor import TripsProcessor
from indra.databases import get_identifiers_url, uniprot_client
from indra.util import read_unicode_csv
from indra.tools import expand_families
from indra.preassembler.hierarchy_manager import hierarchies


logger = logging.getLogger('BioSense')

_indra_path = _indra_path[0]


class BioSense(object):
    """Python API for biosense agent"""
    __slots__ = ['_kinase_list', '_tf_list', '_phosphatase_list']

    def __init__(self):
        self._kinase_list = _read_kinases()
        self._tf_list = _read_tfs()
        self._phosphatase_list = _read_phosphatases()

    def choose_sense(self, ekb):
        """Find possible groundings and potential ambiguities for an ekb-term.

        Args:
        ekb (string): XML for an extraction knowledge base (ekb) term

        Returns:
        dict: (dict of dict: tuple|list) example given below
        {'agents': {'V11519860': (MAP2K1(),
        'ONT::GENE',
        {'HGNC': 'http://identifiers.org/hgnc/HGNC:6840',
        'UP': 'http://identifiers.org/uniprot/Q02750',
        'NCIT': 'http://identifiers.org/ncit/C17808'})},
        'ambiguities': {}}
        """
        agents, ambiguities = _process_ekb(ekb)
        return {'agents': agents, 'ambiguities': ambiguities}

    def choose_sense_category(self, ekb, category):
        """Determine if an agent belongs to a particular category

        Args:
        ekb (string): XML for an extraction knowledge base (ekb) term
        category (string): name of a category. one of 'kinase',
        'kinase activity', 'enzyme', 'transcription factor', 'phosphatase'.

        Returns:
        bool: True if agent is a member of category
        """
        agents, _ = _process_ekb(ekb)
        if len(agents) != 1:
            raise InvalidAgentError
        agent = list(agents.values())[0][0]
        logger.info("Checking {} for category {}".format(agent, category))
        reg_cat = category.lower().replace('-', ' ')
        reg_cat = reg_cat.replace('W::', '').replace('w::', '')
        logger.info("Regularized category to \"{}\".".format(reg_cat))
        if reg_cat in ['kinase', 'kinase activity']:
            output = agent.name in self._kinase_list
        elif reg_cat == 'transcription factor':
            output = agent.name in self._tf_list
        elif reg_cat == 'phosphatase':
            output = agent.name in self._phosphatase_list
        elif reg_cat == 'enzyme':
            output = (agent.name in self._phosphatase_list or
                      agent.name in self._kinase_list)
        else:
            logger.info("Regularized category \"{}\" not recognized: options "
                        "are {}.".format(reg_cat,
                                         ['kinase', 'kinase activity',
                                          'enzyme', 'transcription factor',
                                          'phosphatase']))
            raise UnknownCategoryError
        return output

    def choose_sense_is_member(self, ekb, collection):
        """Determine if an agent is a member of a collection

        Args:
        ekb (string): XML for an extraction knowledge base (ekb) term.
        collection (string): XML for an ekb term of collection for which
        method tests membership.
        """
        agents, _ = _process_ekb(ekb)
        if len(agents) != 1:
            raise InvalidAgentError
        member_agent = list(agents.values())[0][0]
        agents, _ = _process_ekb(collection)
        if len(agents) != 1:
            raise InvalidCollectionError
        collection_agent = list(agents.values())[0][0]
        return member_agent.isa(collection_agent, hierarchies)

    def choose_sense_what_member(self, collection):
        """
        """
        agents, _ = _process_ekb(collection)
        if len(agents) != 1:
            raise InvalidCollectionError
        term_id, (agent, ont_type, urls) = list(agents.items())[0]
        members = _get_members(agent)
        if members is None:
            raise CollectionNotFamilyOrComplexError
        return members

    def get_synonyms(self, ekb):
        """
        """
        try:
            agent = self._get_agent(ekb)
        except Exception as e:
            raise InvalidAgentError
        if agent is None:
            raise InvalidAgentError
        up_id = agent.db_refs.get('UP')
        if not up_id:
            raise InvalidAgentError
        synonyms = uniprot_client.get_synonyms(up_id)
        return synonyms

    @staticmethod
    def _get_agent(agent_ekb):
        tp = TripsProcessor(agent_ekb)
        terms = tp.tree.findall('TERM')
        term_id = terms[0].attrib['id']
        agent = tp._get_agent_by_id(term_id, None)
        return agent


def _get_urls(agent):
    urls = {k: get_identifiers_url(k, v) for k, v in agent.db_refs.items()
            if k != 'TEXT'}
    return urls


def _get_agent_tuples(tp):
    terms = tp.tree.findall('TERM')
    all_agents = {}
    for term in terms:
        term_id = term.attrib['id']
        _, ont_type, _ = trips.processor._get_db_refs(term)
        agent = tp._get_agent_by_id(term_id, None)
        urls = _get_urls(agent)
        all_agents[term_id] = (agent, ont_type, urls)
    return all_agents


def _get_ambiguities(tp):
    terms = tp.tree.findall('TERM')
    all_ambiguities = {}
    for term in terms:
        term_id = term.attrib.get('id')
        _, _, ambiguities = trips.processor._get_db_refs(term)
        if ambiguities:
            all_ambiguities[term_id] = ambiguities
    return all_ambiguities


def _get_members(agent):
    dbname, dbid = agent.get_grounding()
    if dbname not in ['FPLX', 'BE']:
        return None
    eh = hierarchies['entity']
    uri = eh.get_uri(dbname, dbid)
    children_uris = sorted(eh.get_children(uri))
    children_agents = [expand_families._agent_from_uri(uri)
                       for uri in children_uris]
    return children_agents


def _process_ekb(ekb):
    tp = trips.process_xml(ekb)
    agents = _get_agent_tuples(tp)
    ambiguities = _get_ambiguities(tp)
    return agents, ambiguities


def _read_phosphatases():
    p_table = read_unicode_csv(_indra_path +
                               '/resources/phosphatases.tsv', delimiter='\t')
    # First column is phosphatase names
    # Second column is HGNC ids
    p_names = [row[0] for row in p_table]
    return p_names


def _read_kinases():
    kinase_table = read_unicode_csv(_indra_path + '/resources/kinases.tsv',
                                    delimiter='\t')
    gene_names = [lin[1] for lin in list(kinase_table)[1:]]
    return gene_names


def _read_tfs():
    tf_table = read_unicode_csv(_indra_path +
                                '/resources/transcription_factors.csv')
    gene_names = [lin[1] for lin in list(tf_table)[1:]]
    return gene_names


class InvalidAgentError(ValueError):
    pass


class InvalidCollectionError(ValueError):
    pass


class UnknownCategoryError(ValueError):
    pass


class CollectionNotFamilyOrComplexError(ValueError):
    pass
