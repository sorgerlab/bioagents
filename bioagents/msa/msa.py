import re
import json
import uuid
import pickle
import logging

from collections import defaultdict

from indra.util.statement_presentation import group_and_sort_statements, \
    make_stmt_from_sort_key, stmt_to_english
from bioagents.biosense.biosense import _read_kinases, _read_phosphatases, \
    _read_tfs
from indra import get_config
from indra.statements import Statement, stmts_to_json, Agent, \
    get_all_descendants
from indra.sources import indra_db_rest as idbr

from indra.assemblers.html import HtmlAssembler
from indra.assemblers.graph import GraphAssembler
from indra.assemblers.english.assembler import english_join, \
    statement_base_verb, statement_present_verb, statement_passive_verb

logger = logging.getLogger('MSA')


def _build_verb_map():
    # We first get all statement types
    stmts = get_all_descendants(Statement)
    verb_map = {}
    # These are statement types that aren't binary and therefore don't need
    # to be included in the verb map
    non_binary = ('hasactivity', 'activeform', 'selfmodification',
                  'autophosphorylation', 'transphosphorylation',
                  'event', 'unresolved', 'association', 'complex')
    for stmt in stmts:
        # Get the class name
        name = stmt.__name__
        if name.lower() in non_binary:
            continue
        # Get the base verb form of the statement, e.g., "phosphorylate"
        base_verb = statement_base_verb(name.lower())
        verb_map[base_verb] = {'stmt': name, 'type': 'base'}
        # Get the present form of the statement, e.g., "inhibits"
        present_verb = statement_present_verb(name.lower())
        verb_map[present_verb] = {'stmt': name, 'type': 'present'}
        # Get the passive / state form of the statement, e.g., "activated"
        passive_verb = statement_passive_verb(name.lower())
        verb_map[passive_verb] = {'stmt': name, 'type': 'passive'}
    return verb_map


verb_map = _build_verb_map()


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
    ent_type : str or None
        An entity type e.g., 'protein', 'kinase' describing the type of
        entities that are of interest as other agents in the resulting
        statements.
    params : dict
        A dictionary containing other parameters used by the
        IndraDbRestProcessor.
    valid_name_spaces : list[str] or None
        A list of name spaces in order of preference (most preferable first).
        The special key !OTHER! can be used as a place holder for any other
        grounding not explicitly mentioned. The key !NAME! is  place holder
        for the Agent name (that doesn't appear in db_refs).
        If not provided, the following default list will be
        used: ['HGNC', 'FPLX', 'CHEBI', '!OTHER!', 'TEXT', '!NAME!'].
    """
    def __init__(self, subj, obj, agents, verb, ent_type, params,
                 valid_name_spaces=None):
        self.entities = {}
        self._ns_keys = valid_name_spaces if valid_name_spaces is not None \
            else ['HGNC', 'FPLX', 'CHEBI', '!OTHER!', 'TEXT', '!NAME!']
        self.subj = subj
        self.subj_key = self.get_query_key(subj)
        self.obj = obj
        self.obj_key = self.get_query_key(obj)
        self.agents = agents
        self.agent_keys = [self.get_query_key(e) for e in agents]

        self.verb = verb
        if verb in verb_map:
            self.stmt_type = verb_map[verb]['stmt']
        else:
            self.stmt_type = verb

        self.ent_type = ent_type
        self.filter_agents = params.pop('filter_agents', [])

        self.settings = params
        if not self.subj_key and not self.obj_key and not self.agent_keys:
            raise EntityError("Did not get any usable entity constraints!")
        return

    def get_query_key(self, agent):
        if agent is None:
            return None
        dbi, dbn = self.get_agent_grounding(agent)
        self.entities[agent.name] = (dbi, dbn)
        key = '%s@%s' % (dbi, dbn)
        return key

    def get_agent_grounding(self, agent):
        """If the entity is not already an agent, form an agent."""
        if agent is None:
            return None

        dbn, dbi = None, None
        # Iterate over all the keys in order
        for idx, key in enumerate(self._ns_keys):
            # If we hit OTHER, we need to make sure we only return on keys
            # that don't appear in the tail part of the list
            if key == '!OTHER!':
                low_priority_keys = self._ns_keys[idx+1:]
                for key, value in agent.db_refs.items():
                    if key not in low_priority_keys:
                        dbn, dbi = key, value
                        break
            # If we have name here, we use the Agent name for TEXT search
            elif key == '!NAME!':
                dbn, dbi = 'TEXT', agent.name
                break
            # Otherwise, this is a regular key, and we just look for it in
            # the Agent's db_refs
            elif key in agent.db_refs:
                dbn, dbi = key, agent.db_refs[key]
                break

        if dbn is None:
            raise EntityError(("Could not get valid grounding (%s) for %s "
                               "with db_refs=%s.")
                               % (', '.join(self._ns_keys), agent,
                                  agent.db_refs))
        return dbi, dbn


class StatementFinder(object):
    def __init__(self, *args, **kwargs):
        self._block_default = kwargs.pop('block_default', True)
        self.query = self._regularize_input(*args, **kwargs)
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
        if not self.query.verb:
            processor = \
                idbr.get_statements(subject=self.query.subj_key,
                                    object=self.query.obj_key,
                                    agents=self.query.agent_keys,
                                    **self.query.settings)
        else:
            processor = \
                idbr.get_statements(subject=self.query.subj_key,
                                    object=self.query.obj_key,
                                    agents=self.query.agent_keys,
                                    stmt_type=self.query.stmt_type,
                                    **self.query.settings)
        return processor

    def _filter_stmts(self, stmts):
        """This is an internal function that is applied to filter statements.

        In general, this does nothing, but some sub classes may want to limit
        the statements that are presented. This is applied to both the complete
        statements list (retrieved by `get_statements`) and the sample (gotten
        through `get_sample`).
        """
        return stmts

    def _filter_stmts_for_agents(self, stmts):
        """Internal method to filter statements involving particular agents."""
        if not self.query.filter_agents:
            return stmts

        filtered_stmts = []
        logger.info('Starting agent filter with %d statements' % len(stmts))
        for stmt in stmts:

            # Look for any of the agents we are filtering to
            for filter_agent in self.query.filter_agents:

                # Get the prefered grounding
                dbi, dbn = self.query.get_agent_grounding(filter_agent)

                # Look for a match in any of the statements' agents.
                for agent in self.get_other_agents_for_stmt(stmt,
                                        list(self.query.entities.values())):
                    if agent is None:
                        continue

                    if agent.db_refs.get(dbn) == dbi:
                        filtered_stmts.append(stmt)
                        break  # found one.
                else:
                    continue  # keep looking
                break  # found one.

        logger.info('Finished agent filter with %d statements' %
                    len(filtered_stmts))

        return filtered_stmts

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
        self._statements = self._filter_stmts_for_agents(self._statements)

        return self._statements[:]

    def get_fixed_agents(self):
        """Get a dict of the agents that were used as inputs, keyed by role."""
        raw_dict = {'subject': [self.query.subj], 'object': [self.query.obj],
                    'other': self.query.agents}
        ret_dict = {}
        for role, ag_list in raw_dict.items():
            new_list = [ag for ag in ag_list if ag is not None]
            if new_list:
                ret_dict[role] = new_list
        return ret_dict

    def get_other_agents(self, entities=None, other_role=None, block=None):
        """Find all the resulting agents besides the one given.

        It is assumed that the given entity was one of the inputs.

        Parameters
        ----------
        entities : list[Agent] or None
            Either an original entity string or Agent, or Agent name. This
            method will find other entities that occur within the statements
            besides this one. If None, the entity is assumed to be the original
            queried entity.
        other_role : 'subject', 'object', or None
            The part of speech/role of the other names. Limits the results to
            subjects, if 'subject', objects if 'object', or places no limit
            if None. Default is None.
        block : bool or None
            If True, wait for the processor to finish, else return None if it
            is not done. If None, the default set in the class instantiation
            is used.
        """
        # Check to make sure role is valid.
        if other_role not in ['subject', 'object', None]:
            raise ValueError('Invalid role of type %s: %s'
                             % (type(other_role), other_role))

        # If the entities are not given, get them from the query itself
        query_entities = set(self.query.entities.values())
        if entities:
            query_entities &= set(self.query.get_agent_grounding(e)
                                  for e in entities)

        # Build up a dict of groundings, counting how often they occur.
        counts = defaultdict(lambda: 0)
        oa_dict = defaultdict(list)
        ev_totals = self.get_ev_totals()
        stmts = self.get_statements(block)
        if not stmts:
            return None
        for stmt in stmts:
            other_agents = self.get_other_agents_for_stmt(stmt, query_entities,
                                                          other_role)
            for ag in other_agents:
                gr = self.query.get_agent_grounding(ag)
                counts[gr] += ev_totals.get(stmt.get_hash(), 0)
                oa_dict[gr].append(ag)

        def get_aggregate_agent(agents, dbi, dbn):
            agent = Agent(agents[0].name, db_refs={dbn: dbi})
            return agent

        # Create a list of groundings sorted with the most frequent first.
        # We add t itself as a second element to the tuple to make sure the
        # sort is deterministic, and take -counts so that we don't need to
        # reverse the sort.
        sorted_groundings = \
            list(sorted(counts.keys(), key=lambda t: (-counts[t], t)))
        other_agents = [get_aggregate_agent(oa_dict[gr], *gr) for gr in
                        sorted_groundings]
        return other_agents

    @staticmethod
    def get_other_agents_for_stmt(stmt, query_entities, other_role=None):
        """Return a list of other agents for a given statement."""

        def matches_none(ag):
            """Return True if the given agent doesn't match any of the query
            entities."""
            if ag is None:
                return False
            for dbi, dbn in query_entities:
                if ag is not None and ag.db_refs.get(dbn) == dbi:
                    return False
            return True

        other_agents = []
        # If the role is None, look at all the agents.
        ags = stmt.agent_list()
        if other_role is None:
            # List of agents that don't match any of the query entities
            match_none_others = [ag for ag in ags if matches_none(ag)]
            # Handle a special case in which an agent that isn't matches none
            # needs to be returned. This is relevant for instance if we ask for
            # "things that interact with X" and get back Complex(X,X).
            # In this case len(query_entities) == 1, len(ags) == 2, and
            # match_none_others == [], in this case we add X to the other
            # agent list. In addition, to avoid adding X if the Statement
            # is something like Phosphorylation(None, X), we look at the
            # length of not-none Agents and only add another agent is there
            # is more than 1 not None Agent.
            if len(query_entities) < len(ags) and not match_none_others:
                not_none_agents = [ag for ag in ags if ag is not None]
                if len(not_none_agents) > 1:
                    other_agents.append(not_none_agents[0])
            # Otherwise we add all other agents that do not match any of the
            # query agents.
            else:
                other_agents += match_none_others
        # If the role is specified, look at just those agents.
        else:
            idx = 0 if other_role == 'subject' else 1
            if idx + 1 > len(ags):
                raise ValueError('Could not apply role %s, not enough '
                                 'agents: %s' % (other_role, ags))
            other_agents.append(ags[idx])

        return other_agents

    def get_ev_totals(self):
        """Get a dictionary of evidence total counts from the processor."""
        # Getting statements applies any filters, so the counts are consistent
        # with those filters.
        stmts = self.get_statements(block=False)
        return {stmt.get_hash(): self._processor.get_ev_count(stmt)
                for stmt in stmts}

    def get_source_counts(self):
            stmts = self.get_statements(block=False)
            return {stmt.get_hash(): self._processor.get_source_count(stmt)
                    for stmt in stmts}

    def get_sample(self):
        """Get the sample of statements retrieved by the first query."""
        if not self._sample:
            # A deep copy may be warranted here.
            self._sample = \
                self._filter_stmts(self._processor.statements_sample[:])
        return self._sample[:]

    def describe(self, limit=5, include_negative=True):
        """Turn the results dictionary into a coherent message.

        Parameters
        ----------
        limit : int
            The total number of top merged statements to include as an HTML
            list in the response.
        include_negative : bool
            If True, when no results were found, a sentence is generated
            saying so, otherwise an empty string is returned.
        """
        num_stmts = len(self.get_statements())
        if num_stmts > limit:
            msg = 'Here are the top %d statements I found:\n' % limit
            msg += self.get_summary_stmts_html(num=limit) + '\n'
        elif 0 < num_stmts < limit:
            msg = 'Here are the statements I found:\n'
            msg += self.get_summary_stmts_html() + '\n'
        elif include_negative:
            msg = 'I did not find any statements about that'
        else:
            msg = ''
        return msg

    def get_html_message(self):
        msg = 'The rest of the statements may be found here:\n'
        msg += self.get_html() + '\n'
        return msg

    def get_stmt_types(self):
        """Return the sorted set of types found in the body of statements."""
        stmts = self.get_statements()
        evs = self.get_ev_totals()
        # We count the evidence for each type of statement
        counts = {}
        for stmt in stmts:
            stmt_type = stmt.__class__.__name__.lower()
            ev = evs.get(stmt.get_hash(), 0)
            if stmt_type in counts:
                counts[stmt_type] += ev
            else:
                counts[stmt_type] = ev
        # We finally sort by decreasing evidence count
        sorted_stmt_types = [k for k, v in sorted(counts.items(),
                                                  key=lambda x: x[1],
                                                  reverse=True)]
        return sorted_stmt_types

    def get_summary_stmts(self, num=5):
        """Return the top summarized statements for the query."""
        stmts = self.get_statements()
        # Group statements by participants and type, aggregating evidence
        sorted_groups = group_and_sort_statements(stmts, self.get_ev_totals())
        # Create synthetic summary statements in a list
        summary_stmts = []
        for key, verb, stmts in sorted_groups[:num]:
            summary_stmts.append(make_stmt_from_sort_key(key, verb))
        return summary_stmts

    def get_summary_stmts_html(self, num=5):
        """Return top statements in plain English rendered as an HTML list."""
        stmts = self.get_summary_stmts(num)
        lines = ['<li>%s</li>' % stmt_to_english(stmt) for stmt in stmts]

        # Build the overall html.
        if lines:
            list_html = '<ul>%s</ul>' % ('\n'.join(lines))
        else:
            list_html = ''
        return list_html

    def get_html(self):
        """Get html for these statements."""
        import boto3
        ev_totals = self.get_ev_totals()
        source_counts = self.get_source_counts()
        html_assembler = HtmlAssembler(self.get_statements(),
                                       ev_totals=ev_totals,
                                       source_counts=source_counts,
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

    def filter_other_agent_type(self, stmts, ent_type, other_role=None):
        query_entities = set(self.query.entities.values())
        stmts_out = []
        for stmt in stmts:
            other_agents = \
                self.get_other_agents_for_stmt(stmt,
                                               query_entities=query_entities,
                                               other_role=other_role)

            matches = [entity_type_filter.is_ent_type(agent, ent_type)
                       for agent in other_agents]
            if all(matches):
                stmts_out.append(stmt)
        return stmts_out


class Neighborhood(StatementFinder):
    def _regularize_input(self, entity, **params):
        return StatementQuery(None, None, [entity], None, None, params)

    def summarize(self):
        summary = {'query_agent': self.query.agents[0],
                   'other_agents':
                       self.get_other_agents([self.query.agents[0]])}
        return summary

    def describe(self, max_names=20):
        summary = self.summarize()
        desc = ('Overall, I found that %s interacts with%s ' %
                (summary['query_agent'].name,
                 ', for instance,' if len(summary['other_agents']) > max_names
                 else ''))
        if summary['other_agents'][:max_names]:
            desc += english_join([a.name for a in
                                  summary['other_agents'][:max_names]])
        else:
            desc += 'nothing'
        desc += '. '
        desc += super(Neighborhood, self).describe(include_negative=False)
        return desc


class Activeforms(StatementFinder):
    def _regularize_input(self, entity, **params):
        if 'filter_agents' in params.keys():
            logger.warning("Parameter `filter_agents` is not meaningful for "
                           "Activeforms or PhosActiveforms.")
        return StatementQuery(None, None, [entity], 'ActiveForm', None, params)

    def summarize(self):
        # Note that the generic form of grouped ActiveForm statements is
        # degenerate so we just choose the first few actual statements here
        summary = {'summary_stmts': self.get_statements()[:5]}
        return summary


class PhosActiveforms(Activeforms):
    def __init__(self, *args, **kwargs):
        # Get some extra details if available.
        spec_key_list = ['residue', 'position', 'action', 'polarity']
        self.specs = {k: kwargs.pop(k, None) for k in spec_key_list}

        # Continue with normal init.
        super(PhosActiveforms, self).__init__(*args, **kwargs)
        self._statements = None
        self._sample = []
        return

    def _matching(self, stmt):
        if all(val is None for val in self.specs.values()):
            return True

        if stmt.is_active is not (self.specs['polarity'] == 'activating'):
            return False
        matching_residues = any([
            m.residue == self.specs['residue']
            and m.position == self.specs['position']
            and m.mod_type == self.specs['action']
            for m in stmt.agent.mods])
        return matching_residues

    def _filter_stmts(self, stmts):
        ret_stmts = []
        for stmt in stmts:
            ags = stmt.agent_list()
            if len(ags) != 1:
                logger.warning("Got an unexpected statement with 2 agents "
                               "from query for ActiveForms: %s" % str(stmt))
                continue

            # TODO: this implementation is a bit weird and could probably be
            # simplified/improved.
            ag = ags[0]
            for mc in ag.mods:
                if mc.mod_type == 'phosphorylation' and self._matching(stmt):
                    ret_stmts.append(stmt)
                    break

        return ret_stmts


class BinaryDirected(StatementFinder):
    def _regularize_input(self, source, target, verb=None, **params):
        if 'filter_agents' in params.keys():
            logger.warning("Parameter `filter_agents` is not meaningful for "
                           "Binary queries.")
        return StatementQuery(source, target, [], verb, None, params)

    def summarize(self):
        summary = {'stmt_types': [statement_base_verb(v)
                                  for v in self.get_stmt_types()],
                   'query_subj': self.query.subj,
                   'query_obj': self.query.obj}
        return summary

    def describe(self, limit=None):
        summary = self.summarize()
        if summary['stmt_types']:
            desc = "Overall, I found that %s can %s %s." % \
                   (summary['query_subj'].name,
                    english_join(summary['stmt_types']),
                    summary['query_obj'].name)
        else:
            desc = 'Overall, I found that %s does not affect %s.' % \
                (summary['query_subj'].name, summary['query_obj'].name)
        return desc


class BinaryUndirected(StatementFinder):
    def _regularize_input(self, entity1, entity2, **params):
        if 'filter_agents' in params.keys():
            logger.warning("Parameter `filter_agents` is not meaningful for "
                           "Binary queries.")
        return StatementQuery(None, None, [entity1, entity2], None, None,
                              params)

    def summarize(self):
        overrides = {'increaseamount': 'increase amount',
                     'decreaseamount': 'decrease amount',
                     'gtpactivation': 'GTP-bound activation',
                     'gef': 'GEF interaction',
                     'gap': 'GAP interaction',
                     'complex': 'complex formation'}
        stmt_types = [v if v not in overrides else overrides[v]
                      for v in self.get_stmt_types()]
        summary = {'stmt_types': stmt_types,
                   'query_agents': self.query.agents}
        return summary

    def describe(self, limit=None):
        summary = self.summarize()
        names = [ag.name for ag in summary['query_agents']]
        if summary['stmt_types']:
            desc = "Overall, I found that %s and %s interact in the " \
                   "following ways: " % tuple(names)
            desc += (english_join(summary['stmt_types']) + '.')
        else:
            desc = 'I couldn\'t find evidence that %s and %s interact.' \
                   % tuple(names)
        return desc


class FromSource(StatementFinder):
    def _regularize_input(self, source, verb=None, ent_type=None, **params):
        return StatementQuery(source, None, [], verb, ent_type, params)

    def summarize(self):
        if self.query.stmt_type:
            stmt_type = statement_base_verb(self.query.stmt_type.lower())
        else:
            stmt_type = None
        summary = {'stmt_type': stmt_type,
                   'query_subj': self.query.subj,
                   'other_agents': self.get_other_agents([self.query.subj],
                                                         other_role='object')}
        return summary

    def describe(self, limit=10):
        summary = self.summarize()
        if summary['stmt_type'] is None:
            verb_wrap = ' can affect '
            ps = super(FromSource, self).describe(limit=limit,
                                                  include_negative=False)
        else:
            verb_wrap = ' can %s ' % summary['stmt_type']
            ps = ''
        desc = "Overall, I found that " + summary['query_subj'].name + \
               verb_wrap
        other_names = [a.name for a in summary['other_agents']]

        if len(other_names) > limit:
            # We trim the trailing space of desc here before appending
            desc = desc[:-1] + ', for example, '
            desc += english_join(other_names[:limit]) + '. '
        elif 0 < len(other_names) <= limit:
            desc += english_join(other_names) + '. '
        else:
            desc += 'nothing. '

        desc += ps
        return desc

    def _filter_stmts(self, stmts):
        if self.query.ent_type:
            stmts_out = self.filter_other_agent_type(stmts,
                                                     self.query.ent_type,
                                                     other_role='object')
            return stmts_out
        else:
            return stmts


class ToTarget(StatementFinder):
    def _regularize_input(self, target, verb=None, ent_type=None, **params):
        return StatementQuery(None, target, [], verb, ent_type, params)

    def summarize(self):
        if self.query.stmt_type:
            stmt_type = statement_base_verb(self.query.stmt_type.lower())
        else:
            stmt_type = None
        summary = {
            'stmt_type': stmt_type,
            'query_obj': self.query.obj,
            'other_agents': self.get_other_agents([self.query.obj],
                                                  other_role='subject')
        }
        return summary

    def describe(self, limit=5):
        summary = self.summarize()
        if summary['stmt_type'] is None:
            verb_wrap = ' can affect '
            ps = super(ToTarget, self).describe(limit=limit,
                                                include_negative=False)
        else:
            verb_wrap = ' can %s ' % summary['stmt_type']
            ps = ''

        desc = "Overall, I found that"
        other_names = [a.name for a in summary['other_agents']]
        if len(other_names) > limit:
            desc += ', for example, '
            desc += english_join(other_names[:limit])
        elif 0 < len(other_names) <= limit:
            desc += ' ' + english_join(other_names)
        else:
            desc += ' nothing'
        desc += verb_wrap
        desc += summary['query_obj'].name + '. '

        desc += ps
        return desc

    def _filter_stmts(self, stmts):
        # First we filter for None objects
        stmts_out = [s for s in stmts if s.agent_list()[0] is not None]
        if self.query.ent_type:
            stmts_out = self.filter_other_agent_type(stmts_out,
                                                     self.query.ent_type,
                                                     other_role='subject')
        return stmts_out


class ComplexOneSide(StatementFinder):
    def _regularize_input(self, entity, ent_type=None, **params):
        return StatementQuery(None, None, [entity], 'Complex', ent_type,
                              params)

    def summarize(self):
        summary = {'query_agent': self.query.agents[0],
                   'other_agents':
                       self.get_other_agents([self.query.agents[0]]),
                   'stmt_type': 'complex'}
        return summary

    def describe(self, max_names=20):
        summary = self.summarize()
        desc = "Overall, I found that %s can be in a complex with " % \
               summary['query_agent'].name
        desc += english_join([a.name for a in
                              summary['other_agents'][:max_names]])
        desc += '.'
        return desc

    def _filter_stmts(self, stmts):
        # First we filter for None objects
        if self.query.ent_type:
            stmts_out = self.filter_other_agent_type(stmts,
                                                     self.query.ent_type)
            return stmts_out
        else:
            return stmts


class _Commons(StatementFinder):
    _role = NotImplemented
    _name = NotImplemented

    def __init__(self, *args, **kwargs):
        assert self._role in ['SUBJECT', 'OBJECT', 'OTHER']
        self.commons = {}
        super(_Commons, self).__init__(*args, **kwargs)
        return

    def _regularize_input(self, *entities, **params):
        return StatementQuery(None, None, list(entities), None, None, params,
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
        kwargs = self.query.settings.copy()
        if 'max_stmts' not in kwargs.keys():
            kwargs['max_stmts'] = 100
        if 'ev_limit' not in kwargs.keys():
            kwargs['ev_limit'] = 2
        if 'persist' not in kwargs.keys():
            kwargs['persist'] = False

        # Run multiple queries, building up a single processor and a dict of
        # agents held in common.
        processor = None
        for ag, ag_key in zip(self.query.agents, self.query.agent_keys):
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
        self._statements = self._filter_stmts_for_agents(self._statements)
        return self._statements

    def get_common_entities(self):
        return [ag_name for ag_name in self.commons.keys()]

    def summarize(self):
        summary = {'query_agents': self.query.agents,
                   'other_agent_names': self.get_common_entities(),
                   'query_direction': self._name}
        return summary

    def describe(self, *args, **kwargs):
        summary = self.summarize()
        desc = "Overall, I found that %s have the following common %s: %s" \
               % (english_join([ag.name for ag in summary['query_agents']]),
                  summary['query_direction'],
                  english_join(summary['other_agent_names']))
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

            logger.info("Choosing find_complex_one_side.")
            return self.find_complex_one_side(entity, **params)

        # Handle more generic (verb-independent) queries.
        if subject and not object and not agents:
            logger.info("Choosing find_from_source.")
            return self.find_from_source(subject, verb, **params)
        elif object and not subject and not agents:
            logger.info("Choosing find_to_target.")
            return self.find_to_target(object, verb, **params)
        elif subject and object and not agents:
            logger.info("Choosing find_binary_directed")
            return self.find_binary_directed(subject, object, verb, **params)
        elif not subject and not object and agents:
            logger.info("Choosing find_binary_undirected.")
            return self.find_binary_undirected(agents[0], agents[1], verb,
                                               **params)
        else:
            logger.error("Could not find a valid endpoint given arguments.")
            raise ValueError("Invalid combination of entity arguments: "
                             "subject=%s, object=%s, agents=%s."
                             % (subject, object, agents))


class EntityTypeFilter(object):
    def __init__(self):
        self.tfs = _read_tfs()
        self.phosphatases = _read_phosphatases()
        self.kinases = _read_kinases()

    def is_ent_type(self, agent, ent_type):
        if ent_type in ('gene', 'protein'):
            return set(agent.db_refs.keys()) & {'UP', 'HGNC', 'FPLX'}
        elif ent_type in ('transcription factor', 'TF'):
            return agent.name in self.tfs
        elif ent_type == 'kinase':
            return agent.name in self.kinases
        elif ent_type == 'phosphatase':
            return agent.name in self.phosphatases
        elif ent_type == 'enzyme':
            return (agent.name in self.phosphatases or
                    agent.name in self.kinases)
        # By default we just return True here, implying not filtering
        # out the agent
        else:
            return True


entity_type_filter = EntityTypeFilter()
