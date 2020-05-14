import logging
import requests
from indra import __path__ as _indra_path
from indra.util import read_unicode_csv
from indra.tools import expand_families
from indra.ontology.bio import bio_ontology
from indra.preassembler.grounding_mapper import standardize


logger = logging.getLogger('BioSense')
_indra_path = _indra_path[0]

try:
    import gilda
    gilda_web = False
except ImportError:
    gilda_web = True


class BioSense(object):
    """Python API for biosense agent"""
    __slots__ = ['_kinase_list', '_tf_list', '_phosphatase_list']

    def __init__(self):
        self._kinase_list = _read_kinases()
        self._tf_list = _read_tfs()
        self._phosphatase_list = _read_phosphatases()

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
        return agent.isa(collection, bio_ontology)

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
        db, id = agent.get_grounding()
        if db is None or id is None:
            raise SynonymsUnknownError('Couldn\'t get grounding for agent'
                                       ' in a namespace for which we have '
                                       'synonyms.')
        return sorted(get_names_gilda(db, id), key=lambda x: len(x))


def get_names_gilda(db, id):
    if gilda_web:
        res = requests.post('http://grounding.indra.bio/get_names',
                            json={'db': db, 'id': id})
        res.raise_for_status()
        return res.json()
    else:
        return gilda.get_names(db, id)


def _get_members(agent):
    if 'FPLX' not in agent.db_refs:
        return None
    dbname, dbid = 'FPLX', agent.db_refs['FPLX']
    children = bio_ontology.get_children(db_name, db_id)
    children_agents = [standardize(Agent(db_id, db_refs={db_name, db_id}))
                       foir db_name, db_id in children]
    return sorted(children_agents, key=lambda x: x.name))


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
