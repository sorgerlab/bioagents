import json
import os
import pickle
import logging
import requests
from collections import defaultdict

from indra.statements import *
from indra.sources.indra_db_rest.query import And, HasType, HasAgent
from indra.assemblers.html.assembler import get_available_source_counts
from indra.util.statement_presentation import _get_available_ev_source_counts, \
    _get_initial_source_counts

from bioagents.msa.exceptions import EntityError


logger = logging.getLogger(__name__)


def load_from_config(config_str):
    config_type, config_val = config_str.split(':', maxsplit=1)
    logger.info('Running MSA in %s mode' % config_type)
    if config_type == 'emmaa':
        model_name = config_val
        url = ('https://emmaa.s3.amazonaws.com/assembled/%s/'
               'latest_statements_%s.json' % (model_name, model_name))
        res = requests.get(url)
        stmts = stmts_from_json(res.json())
        return LocalQueryProcessor(stmts)
    elif config_type == 'pickle':
        with open(config_val, 'rb') as fh:
            stmts = pickle.load(fh)
            return LocalQueryProcessor(stmts)
    elif config_type == 'service':
        return QueryProcessorClient(config_val)
    elif config_type == 'neo4j':
        return Neo4jClient(config_val)
    else:
        raise ValueError('Invalid config_str: %s' % config_str)


class LocalQueryProcessor:
    def __init__(self, all_stmts):
        self.all_stmts = all_stmts
        self._stmts_lookup = self._build_lookups()
        self.statements = []

    def get_statements(self, subject=None, object=None, agents=None,
                       stmt_type=None, **ignored_kwargs):
        all_stmts = None
        if subject:
            subj_stmts = self._get_stmts_by_key_role(
                self._tuple_from_at_key(subject), 'SUBJECT')
            all_stmts = subj_stmts

        if object:
            obj_stmts = self._get_stmts_by_key_role(
                self._tuple_from_at_key(object), 'OBJECT')
            all_stmts = obj_stmts

        if subject and object:
            all_stmts = self._get_intersection(subj_stmts, obj_stmts)

        if agents:
            ag1_stmts = self._get_stmts_by_key_role(
                self._tuple_from_at_key(agents[0]), None)
            if len(agents) > 1:
                ag2_stmts = self._get_stmts_by_key_role(
                    self._tuple_from_at_key(agents[1]), None)
                all_stmts = self._get_intersection(ag1_stmts, ag2_stmts)
            else:
                all_stmts = ag1_stmts

        if all_stmts is None:
            raise EntityError("Did not get any usable entity constraints!")

        stmts = self._filter_for_type(all_stmts, stmt_type)
        stmts = self.sort_statements(stmts)
        self.statements = stmts
        return self

    def get_statements_from_query(self, query, **ignored_kwargs):
        all_stmts = None
        logger.info('Running query: %s' % query)
        if isinstance(query, And):
            # Sort the queries to ensure that type queries come last.
            q_list = sorted(query.queries,
                            key=lambda q: 1 if isinstance(q, HasType) else 0)
            for sub_query in q_list:
                all_stmts = self._filter_stmts_by_query(sub_query, all_stmts)
        elif isinstance(query, HasAgent):
            all_stmts = self._filter_stmts_by_query(query, all_stmts)
        else:
            raise EntityError("Could not form a usable query from given "
                              "constraints.")
        logger.info('Found %d statements from query' % len(all_stmts))
        self.statements = all_stmts
        return self

    def _filter_stmts_by_query(self, query, all_stmts):
        logger.info('Running subquery: %s' % query)
        if isinstance(query, HasAgent):
            stmts = \
                self._get_stmts_by_key_role((query.namespace, query.agent_id),
                                            query.role)
            if all_stmts:
                return self._get_intersection(all_stmts, stmts)
            else:
                return stmts
        elif isinstance(query, HasType):
            return self._filter_for_type(all_stmts, query.stmt_types[0])
        else:
            logger.warning("Query {query} not handled.")
            return all_stmts

    def sort_statements(self, stmts):
        stmts = sorted(stmts, key=lambda s: len(s.evidence),
                       reverse=True)
        return stmts

    def _filter_for_type(self, stmts, stmt_type=None):
        if not stmt_type:
            return stmts
        return list(filter(lambda x: x.__class__.__name__ == stmt_type,
                           stmts))

    def _get_stmts_by_key_role(self, key, role):
        stmts = self._stmts_lookup.get(key)
        if not stmts:
            return []
        return [s for s, r in stmts if role is None or r == role]

    def _get_intersection(self, stmts1, stmts2):
        sh1 = {stmt.get_hash(): stmt for stmt in stmts1}
        sh2 = {stmt.get_hash(): stmt for stmt in stmts2}
        match = set(sh1.keys()) & set(sh2.keys())
        return [s for k, s in sh1.items() if k in match]

    def _tuple_from_at_key(self, at_key):
        db_id, db_ns = at_key.split('@')
        return db_ns, db_id

    def _build_lookups(self):
        stmts_lookup = defaultdict(list)
        for stmt in self.all_stmts:
            agents = stmt.agent_list()
            for idx, agent in enumerate(agents):
                if agent is None:
                    continue
                role = self._get_agent_role(stmt, idx)
                keys = self._get_agent_keys(agent)
                for key in keys:
                    stmts_lookup[key].append((stmt, role))
        return stmts_lookup

    def _get_agent_role(self, stmt, idx):
        if isinstance(stmt, (RegulateAmount, RegulateActivity,
                             Modification, Conversion, Gap, Gef)):
            return 'SUBJECT' if idx == 0 else 'OBJECT'
        elif isinstance(stmt, Complex):
            return 'SUBJECT'
        elif isinstance(stmt, (ActiveForm, Translocation,
                               SelfModification)):
            return 'OTHER'
        else:
            assert False, stmt

    def _get_agent_keys(self, agent):
        db_ns, db_id = agent.get_grounding()
        if db_ns and db_id:
            return [(db_ns, db_id), ('NAME', agent.name),
                    # TODO: this could be replaced by actual text
                    ('TEXT', agent.name)]
        else:
            keys = []
            if 'TEXT' in agent.db_refs:
                keys.append(('TEXT', agent.db_refs['TEXT']))
            keys.append(('NAME', agent.name))
            return keys

    def get_source_counts(self):
        return get_available_source_counts(self.statements)

    def get_source_count(self, stmt):
        return _get_available_ev_source_counts(stmt.evidence)

    def get_ev_count(self, stmt):
        return len(stmt.evidence)

    def get_ev_counts(self):
        return {s.get_hash(): len(s.evidence) for s in self.statements}

    def wait_until_done(self, timeout=None):
        return

    def is_working(self):
        return False

    def merge_results(self, np):
        self.statements += np.statements


class QueryProcessorClient(LocalQueryProcessor):
    def __init__(self, url):
        self.url = url
        self.statements = []
        self.source_counts = {}

    def _get_stmts_by_key_role(self, key, role):
        role = {'SUBJECT': 'SUBJ', 'OBJECT': 'OBJ', 'OTHER': 'AGENT'}.get(role, 'AGENT')
        url = self.url + ('?ns=%s&id=%s' % key) + \
            ('' if not role else '&role=%s' % role)
        res = requests.get(url)
        return self._process_result(res.json())

    def _process_result(self, res_json):
        stmtsj, source_counts = res_json
        for sj, sc in zip(stmtsj, source_counts):
            mkh = int(sj['matches_hash'])
            if mkh not in self.source_counts:
                self.source_counts[mkh] = _get_initial_source_counts()
            for source, num in sc.items():
                self.source_counts[mkh][source] += num
        return stmts_from_json(stmtsj)

    def get_source_counts(self):
        return self.source_counts

    def get_source_count(self, stmt):
        return self.source_counts.get(stmt.get_hash())

    def get_ev_count(self, stmt):
        return sum(self.get_source_count(stmt).values())

    def get_ev_counts(self):
        return {s.get_hash(): self.get_ev_count(s) for s in self.statements}


class Neo4jClient(QueryProcessorClient):
    def __init__(self, config):
        self.statements = []
        self.source_counts = {}
        self.n4jc = None
        self.resolver = None
        self._get_client()

    def _get_client(self):
        from indra_cogex.client.neo4j_client import Neo4jClient as NC
        self.n4jc = NC()

    def _get_stmts_by_key_role(self, key, role):
        logger.info('Looking up key: %s' % str(key))
        if role == 'SUBJECT':
            rels = self.n4jc.get_target_relations(source=key,
                relation='indra_rel', source_type='BioEntity',
                target_type='BioEntity')
        elif role == 'OBJECT':
            rels = self.n4jc.get_source_relations(target=key,
                relation='indra_rel', source_type='BioEntity',
                target_type='BioEntity')
        else:
            rels = self.n4jc.get_all_relations(node=key,
                relation='indra_rel', node_type='BioEntity',
                other_type='BioEntity')
        stmts = self._process_relations(rels)
        logger.info('Found a total of %d stmts with %s: %s'
                    % (len(stmts), role, str(key)))
        return stmts

    def _process_relations(self, relations):
        stmt_jsons = []
        for rel in relations:
            mkh = rel.data.get('stmt_hash')
            stmt_json = json.loads(_str_escaping(rel.data.get('stmt_json')))
            source_counts = json.loads(rel.data.get('source_counts'))
            stmt_jsons.append(stmt_json)
            if mkh not in self.source_counts:
                self.source_counts[mkh] = _get_initial_source_counts()
            for source, num in source_counts.items():
                self.source_counts[mkh][source] += num
        return stmts_from_json(stmt_jsons)


class ResourceManager:
    """Manages local query resources by key so they are only in memory once."""
    def __init__(self, preloads=None):
        self.resources = {}
        if preloads:
            for preload_key in preloads:
                self.get_resoure(preload_key)

    def get_resoure(self, key):
        """Return a resource from cache or by loading it and caching it."""
        resource = self.resources.get(key)
        if resource:
            logger.info('Returning resource %s from cache' % key)
            return resource
        logger.info('Loading resource %s' % key)
        resource = load_from_config(key)
        self.resources[key] = resource
        return resource


MSA_CORPUS_PRELOADS = os.environ.get('MSA_CORPUS_PRELOAD_CONFIG')
preloads = MSA_CORPUS_PRELOADS.split(',') if MSA_CORPUS_PRELOADS else None

resource_manager = ResourceManager(preloads=preloads)


def _str_escaping(s: str) -> str:
    """Remove double escaped characters and other escaping artifacts."""
    return s.replace(
        '\\\\', '\\').replace('\\\\', '\\').replace('\\{', '{').replace(
        '\\}', '}')
