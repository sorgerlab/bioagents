import re
import json
import uuid
import boto3
import pickle
import logging

from collections import defaultdict

from indra import get_config
from indra.databases import hgnc_client
from indra.statements import stmts_to_json, Agent
from indra.sources import trips
from indra.sources import indra_db_rest as idbr
from indra.preassembler.grounding_mapper import gm

from indra.assemblers.html import HtmlAssembler
from indra.assemblers.graph import GraphAssembler
from indra.assemblers.english.assembler import EnglishAssembler, _join_list

logger = logging.getLogger('MSA')

mod_map = {'demethylate': 'Demethylation',
           'methylate': 'Methylation',
           'phosphorylate': 'Phosphorylation',
           'dephosphorylate': 'Dephosphorylation',
           'ubiquitinate': 'Ubiquitination',
           'deubiquitinate': 'Deubiquitination',
           'inhibit': 'Inhibition',
           'activate': 'Activation'}

DB_REST_URL = get_config('INDRA_DB_REST_URL')


def get_grounding_from_name(name):
    # See if it's a gene name
    hgnc_id = hgnc_client.get_hgnc_id(name)
    if hgnc_id:
        return 'HGNC', hgnc_id

    # Check if it's in the grounding map
    try:
        refs = gm[name]
        if isinstance(refs, dict):
            for dbn, dbi in refs.items():
                if dbn != 'TEXT':
                    return dbn, dbi
    # If not, search by text
    except KeyError:
        pass

    # If none of these, we try TRIPS
    try:
        tp = trips.process_text(name, service_endpoint='drum-dev')
        terms = tp.tree.findall('TERM')
        if not terms:
            return 'TEXT', name
        term_id = terms[0].attrib['id']
        agent = tp._get_agent_by_id(term_id, None)
        if 'HGNC' in agent.db_refs:
            return 'HGNC', agent.db_refs['HGNC']
        if 'FPLX' in agent.db_refs:
            return 'FPLX', agent.db_refs['FPLX']
    except Exception:
        return 'TEXT', name
    return 'TEXT', name


class StatementQuery(object):
    def __init__(self, subj, obj, agents, verb, settings):
        self.entities = {}
        self.subj = subj
        self.subj_key = self.get_key(subj)
        self.obj = obj
        self.obj_key = self.get_key(obj)
        self.agents = agents
        self.agent_keys = [self.get_key(ag) for ag in agents]
        self.verb = verb
        self.settings = settings
        return

    def get_key(self, entity):
        """Create a keys from the entity strings."""
        if entity is None:
            return None
        try:
            if isinstance(entity, str):
                dbn, dbi = get_grounding_from_name(entity)
                self.entities[entity] = (dbn, dbi)
            elif isinstance(entity, Agent):
                for key in ['HGNC', 'FPLX', 'CHEBI', 'TEXT']:
                    if key in entity.db_refs.keys():
                        dbn = key
                        dbi = entity.db_refs[key]
                        break
        except Exception as e:
            return None
        return '%s@%s' % (dbi, dbn)


class StatementFinder(object):
    def __init__(self, *args, **kwargs):
        self.block_default = kwargs.pop('block_default', True)
        self.entities = {}
        self.query = self.regularize_input(*args, **kwargs)
        self.processor = self.make_processor()
        logger.info('Got %d statements.' % len(self.statements))
        return

    def regularize_input(self, *args, **kwargs):
        """Convert arbitrary input in subject, object, agents, and verb."""
        raise NotImplementedError

    def make_processor(self):
        if not self.query.verb or self.query.verb not in mod_map:
            processor = \
                idbr.get_statements(subject=self.query.subj_key,
                                    object=self.query.obj_key,
                                    agents=self.query.agent_keys,
                                    **self.query.settings)
        elif self.query.verb in mod_map.keys():
            stmt_type = mod_map[self.query.verb]
            processor = \
                idbr.get_statements(subject=self.query.subj_key,
                                    object=self.query.obj_key,
                                    agents=self.query.ag_keys,
                                    stmt_type=stmt_type,
                                    **self.query.settings)
        return processor

    def get_statements(self, block=None, timeout=10):
        if block is None:
            block = self.block_default

        if block and self.processor.is_working():
            self.processor.wait_until_done(timeout)
            if self.processor.is_working():
                return None

        return self.processor.statements[:]

    def get_sample(self):
        # A deep copy may be warranted here.
        return self.processor.statements_sample[:]

    def describe(self):
        """Turn the results dictionary into a coherent message."""
        msg = 'Here are the top 5 statements I found:\n'
        msg += self.get_summary() + '\n'
        return msg

    def get_html_message(self):
        msg = 'The rest of the statements may be found here:\n'
        msg += self.get_html() + '\n'
        return msg

    def get_summary(self, num=5):
        """List the top statements in plane english."""
        stmts = self.get_statements()
        sentences = ['- ' + EnglishAssembler([stmts[i]]).make_model()
                     for i in range(min(num, len(stmts)))]
        return '\n'.join(sentences)

    def get_html(self):
        """Get html for these statements."""
        html_assembler = HtmlAssembler(self.get_statements(),
                                       db_rest_url=DB_REST_URL)
        html = html_assembler.make_model()
        s3 = boto3.client('s3')
        bucket = 'indrabot-results'
        key = '%s.html' % uuid.uuid4()
        link = 'https://s3.amazonaws.com/%s/%s' % (bucket, key)
        s3.put_object(Bucket=bucket, Key=key, Body=html.encode('utf-8'),
                      ContentType='text/html')
        return link

    def get_tsv(self):
        """Get a string of the tsv for these statements."""
        msg = ''
        for stmt in self.get_statements():
            if not stmt.evidence:
                logger.warning('Statement %s without evidence' % stmt.uuid)
                txt = ''
                pmid = ''
            else:
                txt = stmt.evidence[0].text if stmt.evidence[0].text else ''
                pmid = stmt.evidence[0].pmid if stmt.evidence[0].pmid else ''
            line = '%s\t%s\t%s\n' % (stmt, txt, pmid)
            msg += line
        return msg

    def get_pickle(self):
        """Generate a pickle file, and return the file name."""
        fname = 'indrabot.pkl'
        with open(fname, 'wb') as fh:
            pickle.dump(self.get_statements(), fh)
        return fname

    def get_pdf_graph(self):
        """Save a graph made with GraphAssembler as pdf, return file name."""
        fname = 'indrabot.pdf'
        ga = GraphAssembler(self.get_statements())
        ga.make_model()
        ga.save_pdf(fname)
        return fname

    def get_json(self):
        """Generate statement jsons and return the json bytes."""
        msg = json.dumps(stmts_to_json(self.get_statements()), indent=1)
        return msg

    def get_unique_verb_list(self):
        """Get the set of statement types found in the body of statements."""
        overrides = {'increaseamount': 'increase amount',
                     'decreaseamount': 'decrease amount',
                     'gtpactivation': 'GTP-bound activation',
                     'gef': 'GEF interaction',
                     'gap': 'GAP interaction',
                     'complex': 'complex formation'}
        stmt_types = {stmt.__class__.__name__.lower() for stmt in
                      self.get_statements()}
        verbs = {st if st not in overrides else overrides[st]
                 for st in stmt_types}
        return list(verbs)

    def get_other_names(self, entity):
        """Find all the resulting agents besides the one given.

        It is assumed that the given entity was one of the inputs.
        """
        dbn, dbi = self.entities[entity]
        name_dict = defaultdict(lambda: 0)
        for s in self.get_statements():
            for ag in s.agent_list():
                if ag is not None and ag.db_refs.get(dbn) != dbi:
                    name_dict[ag.name] += 1
        names = list(sorted(name_dict.keys(), key=lambda t: name_dict[t],
                            reverse=True))
        return names


class Neighborhood(StatementFinder):
    def regularize_input(self, entity):
        return StatementQuery(None, None, [entity], None)

    def describe(self, max_names=20):
        desc = super(Neighborhood, self).describe()
        desc += "\nOverall, I found the following entities in the " \
                "neighborhood of %s: " % self.query.agents[0]
        other_names = self.get_other_names(self.query.agents[0])
        desc += _join_list(other_names[:max_names])
        desc += '.'
        return desc


class Activeforms(StatementFinder):
    def regularize_input(self, entity, **params):
        return StatementQuery(None, None, [entity], 'ActiveForm', params)


class PhosActiveforms(Activeforms):
    def __init__(self, *args, **kwargs):
        super(PhosActiveforms, self).__init__(*args, **kwargs)
        self._statements = []
        self._sample = []
        return

    def _filter_stmts(self, stmts):
        ret_stmts = []
        for stmt in stmts:
            for mc in stmt.agent.mods:
                if mc.mod_type == 'phosphorylation':
                    ret_stmts.append(stmt)
        return ret_stmts

    def get_statements(self, *args, **kwargs):
        if not self._statements:
            stmts = \
                super(PhosActiveforms, self).get_statements(*args, **kwargs)
            if stmts:
                self._statements = self._filter_stmts(stmts)
        return self._statements

    def get_sample(self, *args, **kwargs):
        if not self._sample:
            stmts = \
                super(PhosActiveforms, self).get_statements(*args, **kwargs)
            if stmts:
                self._sample = self._filter_stmts(stmts)
        return self._sample


class BinaryDirected(StatementFinder):
    def regularize_input(self, subject, object, verb=None, **params):
        return StatementQuery(subject, object, [], verb, params)

    def describe(self):
        desc = "Overall, I found that %s can have the following effects on " \
               "%s: " % (self.query.subj, self.query.obj)
        desc += _join_list(self.get_unique_verb_list()) + '.'
        return desc


class BinaryUndirected(StatementFinder):
    def regularize_input(self, entity1, entity2, **params):
        return StatementQuery(None, None, [entity1, entity2], None, params)

    def describe(self):
        desc = "Overall, I found that %s and %s interact in the following " \
               "ways: " % (self.query.agents[0], self.query.agents[1])
        desc += _join_list(self.get_unique_verb_list()) + '.'
        return desc


class FromSource(StatementFinder):
    def regularize_input(self, source, verb=None, **params):
        return StatementQuery(source, None, [], verb, params)


class ToTarget(StatementFinder):
    def regularize_input(self, target, verb=None, **params):
        return StatementQuery(None, target, [], verb, params)


class ComplexOneSide(StatementFinder):
    def regularize_input(self, entity, **params):
        return StatementQuery(None, None, [entity], 'Complex', params)

    def describe(self, max_names=20):
        desc = "Overall, I found that %s can be in a complex with: "
        other_names = self.get_other_names(self.query.agents[0])
        desc += _join_list(other_names[:max_names])
        return desc


def un_camel(name):
    """Convert CamelCase to snake_case.

    Solution found on stackoverflow:
    https://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-snake-case
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class MSA(object):
    """This is a class that organizes and manages mechanism searches.

    Many methods are automatically generated from the children of
    StatementFinder. This include:

        find_neighborhood(entity)
        find_activeforms(entity)
        find_phos_activeforms(entity)
        find_binary_directed(subject, object, verb)
        find_binary_undirected(agent_0, agent_1, verb)
        find_from_source(subject, verb)
        find_to_target(object, verb)
        find_complex_one_side(entity)

    In addition, a more general capability, which attempts to map automatically
    given the input is defined:

        find_mechanism_from_input(subject, object, agents, verb)
    """
    __prefix = 'find_'

    def __init__(self):
        self.__option_dict = {un_camel(c.__class__.__name__): c
                              for c in StatementFinder.__subclasses__()}
        return

    def find_mechanisms(self, method, *args, **kwargs):
        if method in self.__option_dict.key():
            FinderClass = self.__option_dict[method]
            finder = FinderClass(*args, **kwargs)
            return finder
        else:
            raise ValueError("No method: %s." % method)

    def __getattribute__(self, item):
        """Automatically generate functions from the above."""
        if item.startswith(self.__prefix):
            key = item[len(self.__prefix):]
            if key in self.option_dict.keys():
                FinderClass = self.__option_dict[key]
                return FinderClass
            else:
                return super(MSA, self).__getattribute__(item)
        else:
            return super(MSA, self).__getattribute__(item)

    def find_mechanism_from_input(self, subject=None, object=None, agents=None,
                                  verb=None, **params):
        """Get statements, automatically mapping to an appropriate endpoint."""
        # Ensure there are at most 2 agents.
        if agents and len(agents) > 2:
            raise ValueError("Cannot search for mechanisms with more than 2 "
                             "agents (currently).")

        # Look for complexes.
        if verb == 'Complex' and (subject or len(agents) == 1):
            if object:
                raise ValueError('Cannot search for the object of a Complex.')

            # Handle the case where an agent is added without keyword.
            if subject and not agents:
                entity = subject
            # Handle the case where someone defines a list of agents.
            elif agents and not subject:
                entity = agents[0]
            # Someone defined both a subject and agents.
            else:
                raise ValueError('Cannot set both subject and agents to '
                                 'search for complexes.')

            return self.find_complex_one_side(entity, **params)

        # Handle more generic (verb-independent) queries.
        if subject and not object and not agents:
            return self.find_from_subject(subject, verb, **params)
        elif object and not subject and not agents:
            return self.find_to_target(object, verb, **params)
        elif subject and object and not agents:
            return self.find_binary_directed(subject, object, verb, **params)
        elif not subject and not object and agents:
            return self.find_binary_undirected(agents[0], agents[1], verb,
                                               **params)
        else:
            raise ValueError("Invalid combination of entity arguments: "
                             "subject=%s, object=%s, agents=%s."
                             % (subject, object, agents))


