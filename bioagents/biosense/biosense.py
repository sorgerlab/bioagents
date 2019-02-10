import logging
from indra import __path__ as _indra_path
from indra.sources import trips
from indra.sources.trips.processor import TripsProcessor
from indra.databases import get_identifiers_url, uniprot_client
from indra.util import read_unicode_csv
from indra.tools import expand_families
from indra.preassembler.hierarchy_manager import hierarchies
from indra.preassembler.grounding_mapper import default_grounding_map as gm


logger = logging.getLogger('BioSense')
_indra_path = _indra_path[0]


class BioSense(object):
    """Python API for biosense agent"""
    __slots__ = ['_kinase_list', '_tf_list', '_phosphatase_list',
                 '_fplx_synonyms']

    def __init__(self):
        self._kinase_list = _read_kinases()
        self._tf_list = _read_tfs()
        self._phosphatase_list = _read_phosphatases()
        self._fplx_synonyms = _make_fplx_synonyms()

    def choose_sense(self, agent_ekb):
        """Find possible groundings and potential ambiguities for an ekb-term.

        Parameters
        ----------
        ekb : string
        XML for an extraction knowledge base (ekb) term

        Returns
        -------
        agents, ambiguities: tuple[dict]
        example:
        {'agents': {'V11519860': (MAP2K1(),
        'ONT::GENE',
        {'HGNC': 'http://identifiers.org/hgnc/HGNC:6840',
        'UP': 'http://identifiers.org/uniprot/Q02750',
        'NCIT': 'http://identifiers.org/ncit/C17808'})},
        'ambiguities': {}}

        Raises
        ------

        InvalidAgentError
        If agent_ekb does not correspond to a recognized agent
        """
        agents, ambiguities = _process_ekb(agent_ekb)
        if len(agents) == 0:
            raise InvalidAgentError
        return agents, ambiguities

    def choose_sense_category(self, agent_ekb, category):
        """Determine if an agent belongs to a particular category

        Parameters
        ----------
        agent_ekb : string
        XML for an extraction knowledge base (ekb) term
        category : string
        name of a category. one of 'kinase', 'kinase activity', 'enzyme',
        'transcription factor', 'phosphatase'.

        Returns
        -------
        bool: True if agent is a member of category False otherwise

        Raises
        ------
        InvalidAgentError
        If agent_ekb does not correspond to a recognized agent

        UnknownCategoryError
        -------------------
        If category is not from recognized list
        """
        agents, _ = _process_ekb(agent_ekb)
        if len(agents) != 1:
            raise InvalidAgentError("agent not recognized")
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
            raise UnknownCategoryError("category not recognized")
        return output

    def choose_sense_is_member(self, agent_ekb, collection_ekb):
        """Determine if an agent is a member of a collection

        Parameters
        ----------
        agent_ekb : string
        XML for an extraction knowledge base (ekb) term.
        collection_ekb : string
        XML for the ekb term for a collection method tests for membership

        Returns
        -------
        bool: True is agent is a member of the collection

        Raises
        ------
        InvalidAgentError
        If agent_ekb does not correspond to a recognized agent

        InvalidCollectionError
        If collection_ekb does not correspond to a recognized category
        """
        agents, _ = _process_ekb(agent_ekb)
        if len(agents) != 1:
            raise InvalidAgentError("agent not recognized")
        member_agent = list(agents.values())[0][0]
        agents, _ = _process_ekb(collection_ekb)
        if len(agents) != 1:
            raise InvalidCollectionError("collection not recognized")
        agent, ont_type, _ = list(agents.values())[0]
        if ont_type != 'ONT::PROTEIN-FAMILY':
            raise CollectionNotFamilyOrComplexError
        return member_agent.isa(agent, hierarchies)

    def choose_sense_what_member(self, collection_ekb):
        """Get members of a collection.

        Parameters
        ----------
        collection_ekb : string
        XML for an extraction knowledge base (ekb) term for a family or
        complex (from 'FMPLX' or 'BE')

        Returns
        -------
        members : list[indra.statements.Agent]
        List of agents in collection

        Raises
        ------
        InvalidCollectionError
        If collection_ekb does not correspond to a recognized collection

        CollectionNotFamilyOrComplexError
        collection is not from 'FMPLX' or 'BE'
        """
        agents, _ = _process_ekb(collection_ekb)
        if len(agents) != 1:
            raise InvalidCollectionError("collection not recognized")
        term_id, (agent, ont_type, urls) = list(agents.items())[0]
        members = _get_members(agent)
        if members is None:
            raise CollectionNotFamilyOrComplexError("collection not in 'FMPLX'"
                                                    " or 'BE'")
        return members

    def get_synonyms(self, agent_ekb):
        """Get synonyms of an agent

        Parameters
        -----------
        agent_ekb : str
            XML for an extraction knowledge base (ekb) term for an agent

        Returns
        -------
        synonyms : list[str]
            list of synonyms for the agent

        Raises
        ------
        InvalidAgentError
            agent_ekb does not correspond to a recognized agent
        """
        try:
            agent = self._get_agent(agent_ekb)
        except Exception as e:
            logger.error(e)
            raise InvalidAgentError("agent_ekb not readable by Trips")
        if agent is None:
            raise InvalidAgentError("agent not recognized")
        up_id = agent.db_refs.get('UP')
        fplx_id = agent.db_refs.get('FPLX')
        if up_id:
            synonyms = uniprot_client.get_synonyms(up_id)
        elif fplx_id:
            synonyms = self._fplx_synonyms.get(fplx_id, [])
        else:
            raise SynonymsUnknownError('We don\'t provide synonyms for '
                                       'this type of agent.')

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


def _make_fplx_synonyms():
    fplx_synonyms = {}
    for txt, db_refs in gm.items():
        if not db_refs:
            continue
        fplx_id = db_refs.get('FPLX')
        if fplx_id:
            try:
                fplx_synonyms[fplx_id].append(txt)
            except KeyError:
                fplx_synonyms[fplx_id] = [txt]
    return fplx_synonyms


class InvalidAgentError(ValueError):
    """raised if agent not recognized"""
    pass


class SynonymsUnknownError(ValueError):
    """raised if agent not recognized"""
    pass


class InvalidCollectionError(ValueError):
    """raised if collection not recognized"""
    pass


class UnknownCategoryError(ValueError):
    """raised if category not one of one of 'kinase', 'kinase activity',
    'enzyme', 'transcription factor', 'phosphatase'."""

    pass


class CollectionNotFamilyOrComplexError(ValueError):
    """raised if a collection is not in 'FMPLX' or 'BE'"""
    pass
