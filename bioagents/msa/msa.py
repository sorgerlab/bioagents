import re
import json
import uuid
import boto3
import pickle
import logging

from collections import defaultdict

from bioagents import get_row_data
from indra import get_config
from indra.statements import stmts_to_json, Agent, get_all_descendants
from indra.sources import indra_db_rest as idbr

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


class EntityError(ValueError):
    pass


class StatementQuery(object):
    """This is an object that encapsulates the information used to make a query.

    Parameters
    ----------
    subj, obj : Agent or None
        The subject and object of the causal mechanism to be found. If an
        Agent, the db_refs will be used as grounding. If there is no subject or
        object, subj or obj may be None respectively.
    agents : list[Agent]
        A list of Agents like subj and obj, but without the implication of an
        order. Each element will be treated as above.
    verb : str or None
        A string describing a type of interaction between the subject, object,
        and/or agents. Must be mappable to a subclass of Statement.
    settings : dict
        A dictionary containing other parameters used by the
        IndraDbRestProcessor.
    valid_name_spaces : list[str] or None
        A list of name spaces that are allowed as grounding, in order of
        preference (most preferable first). If None, the default list will be
        used: ['HGNC', 'FPLX', 'CHEBI', 'TEXT'].
    """
    def __init__(self, subj, obj, entities, verb, settings,
                 valid_name_spaces=None):
        self.entities = {}
        self._ns_keys = valid_name_spaces if valid_name_spaces is not None \
            else ['HGNC', 'FPLX', 'CHEBI', 'TEXT']
        self.subj = subj
        self.subj_key = self.get_key(subj)
        self.obj = obj
        self.obj_key = self.get_key(obj)
        self.agents = entities
        self.agent_keys = [self.get_key(e) for e in entities]

        self.verb = verb
        if verb in mod_map.keys():
            self.stmt_type = mod_map[verb]
        else:
            self.stmt_type = verb

        self.settings = settings
        if not self.subj_key and not self.obj_key and not self.agent_keys:
            raise EntityError("Did not get any usable entity constraints!")
        return

    def get_key(self, agent):
        """If the entity is not already an agent, form an agent."""
        if agent is None:
            return None

        # Get the key
        for key in self._ns_keys:
            if key in agent.db_refs.keys():
                dbn = key
                dbi = agent.db_refs[key]
                break
        else:
            raise EntityError("Could not get valid grounding (%s) for %s."
                              % (', '.join(self._ns_keys), agent))
        self.entities[agent.name] = (dbn, dbi)

        return '%s@%s' % (dbi, dbn)


class StatementFinder(object):
    def __init__(self, *args, **kwargs):
        self._block_default = kwargs.pop('block_default', True)
        self._query = self._regularize_input(*args, **kwargs)
        self._processor = self._make_processor()
        self._statements = None
        self._sample = []
        return

    def _regularize_input(self, *args, **kwargs):
        """Convert arbitrary input in subject, object, agents, and verb."""
        raise NotImplementedError

    def _make_processor(self):
        """Create an instance a indra_db_rest processor.

        This method makes use of the `query` attribute.
        """
        if not self._query.verb:
            processor = \
                idbr.get_statements(subject=self._query.subj_key,
                                    object=self._query.obj_key,
                                    agents=self._query.agent_keys,
                                    **self._query.settings)
        else:
            processor = \
                idbr.get_statements(subject=self._query.subj_key,
                                    object=self._query.obj_key,
                                    agents=self._query.agent_keys,
                                    stmt_type=self._query.stmt_type,
                                    **self._query.settings)
        return processor

    def _filter_stmts(self, stmts):
        """This is an internal function that is applied to filter statements.

        In general, this does nothing, but some sub classes may want to limit
        the statements that are presented. This is applied to both the complete
        statements list (retrieved by `get_statements`) and the sample (gotten
        through `get_sample`).
        """
        return stmts

    def get_statements(self, block=None, timeout=10):
        """Get the full list of statements if available."""
        if self._statements is not None:
            return self._statements[:]

        if block is None:
            # This is True by default.
            block = self._block_default

        if self._processor.is_working():
            if block:
                self._processor.wait_until_done(timeout)
                if self._processor.is_working():
                    return None
            else:
                return None

        self._statements = self._filter_stmts(self._processor.statements[:])

        return self._statements[:]

    def get_sample(self):
        """Get the sample of statements retrieved by the first query."""
        if not self._sample:
            # A deep copy may be warranted here.
            self._sample = \
                self._filter_stmts(self._processor.statements_sample[:])
        return self._sample[:]

    def describe(self):
        """Turn the results dictionary into a coherent message."""
        summary = self.get_summary()
        if summary:
            msg = 'Here are the top 5 statements I found:\n'
            msg += self.get_summary() + '\n'
        else:
            msg = 'I did not find any statements about that'
        return msg

    def get_html_message(self):
        msg = 'The rest of the statements may be found here:\n'
        msg += self.get_html() + '\n'
        return msg

    def get_summary(self, num=5):
        """List the top statements in plane english."""
        stmts = self.get_statements()
        row_data = get_row_data(stmts)
        lines = []
        for key, verb, stmts in row_data[:num]:
            # For now, just skip non-subject-object-verb statements.

            if len(key[1:]) == 2:
                line = '<li>%s</li>' % ' '.join([key[1], verb, key[2]])
            else:
                line = '<li>%s among %s</li>' % (verb, ' '.join(key[1:]))
            lines.append(line)

        # Build the overall html.
        list_html = '<ul>%s</ul>' % ('\n'.join(lines))
        return list_html

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

    def get_other_names(self, entity, role=None):
        """Find all the resulting agents besides the one given.

        It is assumed that the given entity was one of the inputs.

        Parameters
        ----------
        entity : str or Agent.
            Either an original entity string or Agent, or Agent name. This
            method will find other entities that occur within the statements
            besides this one.
        role : 'subject', 'object', or None
            The part of speech/role of the other names. Limits the results to
            subjects, if 'subject', objects if 'object', or places no limit
            if None. Default is None.
        """
        # Check to make sure role is valid.
        if role not in ['subject', 'object', None]:
            raise ValueError('Invalid role of type %s: %s'
                             % (type(role), role))

        # Get the namespace and id of the original entity.
        dbn, dbi = self._query.entities[entity.name]

        # Build up a dict of names, counting how often they occur.
        name_dict = defaultdict(lambda: 0)
        for s in self.get_statements():

            # If the role is None, look at all the agents.
            if role is None:
                for ag in s.agent_list():
                    if ag is not None and ag.db_refs.get(dbn) != dbi:
                        name_dict[ag.name] += 1
            # If the role is specified, look at just those agents.
            else:
                idx = 0 if role == 'subject' else 1
                if idx+1 > len(s.agent_list()):
                    raise ValueError('Could not apply role %s, not enough '
                                     'agents: %s' % (role, s.agent_list()))
                ag = s.agent_list()[idx]
                if ag is not None and ag.db_refs.get(dbn) != dbi:
                    name_dict[ag.name] += 1

        # Create a list of names sorted with the most frequent first.
        names = list(sorted(name_dict.keys(), key=lambda t: name_dict[t],
                            reverse=True))
        return names


class Neighborhood(StatementFinder):
    def _regularize_input(self, entity):
        return StatementQuery(None, None, [entity], None)

    def describe(self, max_names=20):
        desc = super(Neighborhood, self).describe()
        desc += "\nOverall, I found the following entities in the " \
                "neighborhood of %s: " % self._query.agents[0].name
        other_names = self.get_other_names(self._query.agents[0].name)
        desc += _join_list(other_names[:max_names])
        desc += '.'
        return desc


class Activeforms(StatementFinder):
    def _regularize_input(self, entity, **params):
        return StatementQuery(None, None, [entity], 'ActiveForm', params)


class PhosActiveforms(Activeforms):
    def __init__(self, *args, **kwargs):
        super(PhosActiveforms, self).__init__(*args, **kwargs)
        self._statements = None
        self._sample = []
        return

    def _filter_stmts(self, stmts):
        ret_stmts = []
        for stmt in stmts:
            ags = stmt.agent_list()
            if len(ags) != 1:
                logger.warning("Got an unexpected statement with 2 agents "
                               "from query for ActiveForms: %s" % str(stmt))
                continue
            ag = ags[0]
            for mc in ag.mods:
                if mc.mod_type == 'phosphorylation':
                    ret_stmts.append(stmt)
        return ret_stmts


class BinaryDirected(StatementFinder):
    def _regularize_input(self, subject, object, verb=None, **params):
        return StatementQuery(subject, object, [], verb, params)

    def describe(self):
        desc = "Overall, I found that %s can have the following effects on " \
               "%s: " % (self._query.subj.name, self._query.obj.name)
        desc += _join_list(self.get_unique_verb_list()) + '.'
        return desc


class BinaryUndirected(StatementFinder):
    def _regularize_input(self, entity1, entity2, **params):
        return StatementQuery(None, None, [entity1, entity2], None, params)

    def describe(self):
        desc = "Overall, I found that %s and %s interact in the following " \
               "ways: " % tuple([ag.name for ag in self._query.agents])
        desc += _join_list(self.get_unique_verb_list()) + '.'
        return desc


class FromSource(StatementFinder):
    def _regularize_input(self, source, verb=None, **params):
        return StatementQuery(source, None, [], verb, params)


class ToTarget(StatementFinder):
    def _regularize_input(self, target, verb=None, **params):
        return StatementQuery(None, target, [], verb, params)


class ComplexOneSide(StatementFinder):
    def _regularize_input(self, entity, **params):
        return StatementQuery(None, None, [entity], 'Complex', params)

    def describe(self, max_names=20):
        desc = "Overall, I found that %s can be in a complex with: "
        other_names = self.get_other_names(self._query.agents[0].name)
        desc += _join_list(other_names[:max_names])
        return desc


class _Commons(StatementFinder):
    _role = NotImplemented
    _name = NotImplemented

    def __init__(self, *args, **kwargs):
        assert self._role in ['SUBJECT', 'OBJECT', 'OTHER']
        self.commons = {}
        super(_Commons, self).__init__(*args, **kwargs)
        return

    def _regularize_input(self, *entities, **params):
        return StatementQuery(None, None, list(entities), None, params,
                              ['HGNC', 'FPLX'])

    def _iter_stmts(self, stmts):
        for stmt in stmts:
            ags = stmt.agent_list()
            if self._role == 'OTHER':
                for other_ag in ags:
                    yield other_ag, stmt
            elif self._role == 'SUBJECT' and len(ags) >= 2:
                yield ags[1], stmt
            elif len(ags):
                yield ags[0], stmt

    def _make_processor(self):
        """This method is overwritten to prevent excessive queries.

        Given N entities, the odds of finding common neighbors among them all
        decrease rapidly as N increases. Thus, if N is 100, you will likely run
        out of common neighbors after only a few queries. This implementation
        takes advantage of that fact, thus preventing hangs in essentially
        trivial cases with large N.
        """
        # Prep the settings with some defaults.
        kwargs = self._query.settings.copy()
        if 'max_stmts' not in kwargs.keys():
            kwargs['max_stmts'] = 100
        if 'ev_limit' not in kwargs.keys():
            kwargs['ev_limit'] = 2
        if 'persist' not in kwargs.keys():
            kwargs['persist'] = False

        # Run multiple queries, building up a single processor and a dict of
        # agents held in common.
        processor = None
        for ag, ag_key in zip(self._query.agents, self._query.agent_keys):
            if ag_key is None:
                continue

            # Make another query.
            kwargs[self._role.lower()] = ag_key
            new_processor = idbr.get_statements(**kwargs)
            new_processor.wait_until_done()

            # Look for new agents.
            for other_ag, stmt in self._iter_stmts(new_processor.statements):
                if other_ag is None or 'HGNC' not in other_ag.db_refs.keys():
                    continue
                other_id = other_ag.name

                # If this is the first pass, init the dict.
                if processor is None and other_id not in self.commons.keys():
                    self.commons[other_id] = {ag.name: [stmt]}
                # Otherwise we can only add to the sub-dicts and their lists.
                elif other_id in self.commons.keys():
                    if ag.name not in self.commons[other_id].keys():
                        self.commons[other_id][ag.name] = []
                    self.commons[other_id][ag.name].append(stmt)

            # If this isn't the first time around, remove all entries that
            # didn't find match this time around.
            if processor is None:
                processor = new_processor
            else:
                self.commons = {other_id: data
                                for other_id, data in self.commons.items()
                                if ag.name in data.keys()}
                processor.merge_results(new_processor)

            # If there's nothing left in common, it won't get better.
            if not self.commons:
                break

        return processor

    def get_statements(self, block=None, timeout=10):
        if self._statements is None:
            self._statements = [s for data in self.commons.values()
                                for s_list in data.values()
                                for s in s_list]
        return self._statements

    def get_common_entities(self):
        return [ag_name for ag_name in self.commons.keys()]

    def describe(self):
        desc = "Overall, I found that %s have the following common %s: %s" \
               % (_join_list([ag.name for ag in self.query.agents]),
                  self._name, _join_list(self.get_common_entities()))
        return desc


class CommonUpstreams(_Commons):
    _role = 'OBJECT'
    _name = 'upstreams'


class CommonDownstreams(_Commons):
    _role = 'SUBJECT'
    _name = 'downstreams'


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
    def __init__(self):
        self.__option_dict = {}
        for cls in get_all_descendants(StatementFinder):
            if cls.__name__.startswith('_'):
                continue
            self.__option_dict[un_camel(cls.__name__)] = cls
        return

    def find_mechanisms(self, method, *args, **kwargs):
        if method in self.__option_dict.keys():
            FinderClass = self.__option_dict[method]
            finder = FinderClass(*args, **kwargs)
            return finder
        else:
            raise ValueError("No method: %s." % method)

    def __getattribute__(self, item):
        """Automatically generate functions from the above."""
        prefix = 'find_'
        if item.startswith(prefix):
            key = item[len(prefix):]
            if key in self.__option_dict.keys():
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
            return self.find_from_source(subject, verb, **params)
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


