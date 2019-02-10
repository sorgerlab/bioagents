import sys
import logging
import indra
from .biosense import BioSense, _get_urls
from .biosense import InvalidAgentError, UnknownCategoryError, \
    SynonymsUnknownError
from .biosense import InvalidCollectionError, CollectionNotFamilyOrComplexError
from bioagents import Bioagent
from kqml import KQMLPerformative, KQMLList, KQMLString


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
             'GET-SYNONYMS']

    def respond_choose_sense(self, content):
        """Return response content to choose-sense request."""
        ekb = content.gets('ekb-term')
        msg = KQMLPerformative('SUCCESS')
        try:
            agents, ambiguities = self.bs.choose_sense(ekb)
        except InvalidAgentError:
            logger.info("agent not recognized:\n{}\n".format(ekb))
        else:
            kagents = []
            for term_id, agent_tuple in agents.items():
                kagent = get_kagent(agent_tuple, term_id)
                kagents.append(kagent)
            msg.set('agents', KQMLList(kagents))
        if ambiguities:
            ambiguities_msg = get_ambiguities_msg(ambiguities)
            msg.set('ambiguities', ambiguities_msg)
        return msg

    def respond_choose_sense_category(self, content):
        """Return response content to choose-sense-category request."""
        ekb = content.gets('ekb-term')
        category = content.gets('category')
        try:
            in_category = self.bs.choose_sense_category(ekb, category)
        except InvalidAgentError:
            msg = make_failure('INVALID_AGENT')
        except UnknownCategoryError:
            msg = make_failure('UNKNOWN_CATEGORY')
        else:
            msg = KQMLList('SUCCESS')
            msg.set('in-category',
                    'TRUE' if in_category else 'FALSE')
        return msg

    def respond_choose_sense_is_member(self, content):
        """Return response content to choose-sense-is-member request."""
        agent_ekb = content.gets('ekb-term')
        collection_ekb = content.gets('collection')
        try:
            is_member = self.bs.choose_sense_is_member(agent_ekb,
                                                       collection_ekb)
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
        ekb = content.gets('collection')
        try:
            members = self.bs.choose_sense_what_member(ekb)
        except InvalidCollectionError:
            msg = make_failure('INVALID_COLLECTION')
        except CollectionNotFamilyOrComplexError:
            msg = make_failure('COLLECTION_NOT_FAMILY_OR_COMPLEX')
        else:
            kagents = [get_kagent((m, 'ONT::PROTEIN', _get_urls(m)))
                       for m in members]
            msg = KQMLList('SUCCESS')
            msg.set('members', KQMLList(kagents))
        return msg

    def respond_get_synonyms(self, content):
        """Respond to a query looking for synonyms of a protein."""
        ekb = content.gets('entity')
        try:
            synonyms = self.bs.get_synonyms(ekb)
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


def get_kagent(agent_tuple, term_id=None):
    agent, ont_type, urls = agent_tuple
    db_refs = '|'.join('%s:%s' % (k, v) for k, v in
                       agent.db_refs.items())
    kagent = KQMLList(term_id) if term_id else KQMLList()
    kagent.sets('name', agent.name)
    kagent.sets('ids', db_refs)
    url_parts = [KQMLList([':name', KQMLString(k),
                           ':dblink', KQMLString(v)])
                 for k, v in urls.items()]
    url_list = KQMLList()
    for url_part in url_parts:
        url_list.append(url_part)
    kagent.set('id-urls', url_list)
    kagent.set('ont-type', ont_type)
    return kagent


def get_ambiguities_msg(ambiguities):
    sa = []
    for term_id, ambiguity in ambiguities.items():
        msg = KQMLList(term_id)

        pr = ambiguity[0]['preferred']
        pr_dbids = '|'.join([':'.join((k, v)) for
                             k, v in pr['refs'].items()])
        term = KQMLList('term')
        term.set('ont-type', pr['type'])
        term.sets('ids', pr_dbids)
        term.sets('name', pr['name'])
        msg.set('preferred', term)

        alt = ambiguity[0]['alternative']
        alt_dbids = '|'.join([':'.join((k, v)) for
                              k, v in alt['refs'].items()])
        term = KQMLList('term')
        term.set('ont-type', alt['type'])
        term.sets('ids', alt_dbids)
        term.sets('name', alt['name'])
        msg.set('alternative', term)

        sa.append(msg)

    ambiguities_msg = KQMLList(sa)
    return ambiguities_msg


def make_failure(reason):
    msg = KQMLList('FAILURE')
    msg.set('reason', reason)
    return msg


if __name__ == "__main__":
    BioSense_Module(argv=sys.argv[1:])
