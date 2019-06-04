import logging
from indra import __path__ as _indra_path
from indra.databases import uniprot_client
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

    def choose_sense_category(self, agent, category):
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
        logger.info('Checking %s for category %s' % (agent, category))
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
            logger.info("Regularized category %s not recognized: options "
                        "are %s." % (reg_cat, ['kinase', 'kinase activity',
                                               'enzyme', 'transcription factor',
                                               'phosphatase']))
            raise UnknownCategoryError('category not recognized')
        return output

    def choose_sense_is_member(self, agent, collection):
        """Determine if an agent is a member of a collection

        Parameters
        ----------
        agent : Agent
            An Agent whose membership is to be checked
        collection : Agent
            Collection in which to check if the agent is a member.

        Returns
        -------
        bool
            True if agent is a member of the collection

        Raises
        ------
        CollectionNotFamilyOrComplexError
            If collection does not correspond to a FamPlex entry
        """
        if 'FPLX' not in collection.db_refs:
            raise CollectionNotFamilyOrComplexError(
                '%s is not a family or complex' % collection)
        return agent.isa(collection, hierarchies)

    def choose_sense_what_member(self, collection):
        """Get members of a collection.

        Parameters
        ----------
        collection : Agent
            Collection to check for members.

        Returns
        -------
        members : list[indra.statements.Agent]
            List of agents in collection

        Raises
        ------
        CollectionNotFamilyOrComplexError
            If collection does not correspond to a FamPlex entry
        """
        if 'FPLX' not in collection.db_refs:
            raise CollectionNotFamilyOrComplexError(
                '%s is not a family or complex' % collection)
        members = _get_members(collection)
        return members

    def get_synonyms(self, agent):
        """Get synonyms of an agent

        Parameters
        -----------
        agent : Agent
            An Agent whose synonyms are to be returned.

        Returns
        -------
        synonyms : list[str]
            List of synonyms for the agent

        Raises
        ------
        SynonymsUnknownError
            We don't provide synonyms for this type of agent.
        """
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


def _get_members(agent):
    if 'FPLX' not in agent.db_refs:
        return None
    dbname, dbid = 'FPLX', agent.db_refs['FPLX']
    eh = hierarchies['entity']
    uri = eh.get_uri(dbname, dbid)
    children_uris = sorted(eh.get_children(uri))
    children_agents = [expand_families._agent_from_uri(uri)
                       for uri in children_uris]
    return children_agents


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
