import logging
import itertools
from copy import deepcopy
import networkx as nx
from indra.databases import hgnc_client
from indra.mechlinker import MechLinker
from indra.statements import *
from indra.sources.indra_db_rest import get_statements
from indra.explanation.model_checker import ModelChecker, stmts_for_path, \
                                            _stmt_from_rule
from indra.assemblers.pysb.assembler import grounded_monomer_patterns


logger = logging.getLogger('model_diagnoser')


class ModelDiagnoser(object):
    def __init__(self, statements, model=None, explain=None):
        self.statements = statements
        self.model = model
        self.explain = explain

    def get_missing_activities(self):
        ml = MechLinker(self.statements)
        ml.gather_explicit_activities()
        suggestions = []
        for stmt in self.statements:
            if isinstance(stmt, (Modification, RegulateActivity,
                                 RegulateAmount)):
                # The subj here is in an "active" position
                subj, obj = stmt.agent_list()
                if subj is None:
                    continue
                subj_base = ml._get_base(subj)
                # If it has any activities but isn't in an active state
                # here
                if subj_base.activity_types and not subj.activity:
                    # We suggest making the subj active in this case
                    suggestion = deepcopy(stmt)
                    act_type = subj_base.activity_types[0]
                    new_subj = deepcopy(subj)
                    new_subj.activity = ActivityCondition(act_type, True)
                    suggestion.set_agent_list([new_subj, obj])
                    suggestions.append(suggestion)
        return suggestions

    def check_explanation(self):
        if self.model is None:
            raise ValueError('check_explanation requires a PySB model.')
        if self.explain is None:
            raise ValueError('check_explanation requires an explanation goal.')
        result = {}
        mc = ModelChecker(self.model, [self.explain])
        try:
            pr = mc.check_statement(self.explain, max_paths=0)
            result['has_explanation'] = pr.path_found
        except Exception as e:
            logger.error("Error checking statement for paths: %s" % str(e))
            result['has_explanation'] = False
        # If we found a path get a path
        if result['has_explanation']:
            try:
                pr = mc.check_statement(self.explain, max_paths=1,
                                        max_path_length=8)
                path_stmts = stmts_for_path(pr.paths[0], self.model,
                                            self.statements)
                result['explanation_path'] = path_stmts
            except Exception as e:
                logger.error("Error getting paths for statement: %s" % str(e))
        # If we don't already have an explanation, see if we can propose one
        else:
            # Get the source rules associated with the statement to explain
            source_rules = []
            subj_mps = grounded_monomer_patterns(self.model,
                                                 self.explain.agent_list()[0])
            for subj_mp in subj_mps:
                source_rules += mc._get_input_rules(subj_mp)
            obs_names = mc.stmt_to_obs[self.explain]
            # If we've got both source rules and observable names, add dummy
            # nodes for the source (connected to all input rules) and the 
            # target (connected to all observables) so we only have to deal
            # with a single source and a single target
            if source_rules and obs_names:
                new_edges = [('SOURCE', sr) for sr in source_rules]
                new_edges += [(on, 'TARGET') for on in obs_names]
                im = mc.get_im()
                im.add_edges_from(new_edges)
                # Now, we know that there is no path between SOURCE and TARGET.
                # Instead, we consider connections among all possible pairs
                # of nodes in the graph and count the number of nodes in
                # the path between source and target:
                best_edge = (None, 0)
                for u, v in itertools.permutations(im.nodes(), 2):
                    # Add the edge to the graph
                    im.add_edge(u, v)
                    # Find longest path between source and target
                    simple_paths = list(nx.all_simple_paths(im, 'SOURCE',
                                                            'TARGET'))
                    simple_paths.sort(key=lambda p: len(p), reverse=True)
                    if simple_paths and len(simple_paths[0]) > best_edge[1]:
                        best_edge = ((u, v), len(simple_paths[0]))
                    # Now remove the edge we added before going on to the next
                    im.remove_edge(u, v)
                if best_edge[0]:
                    result['connect_rules'] = best_edge[0]
                    u_stmt = _stmt_from_rule(self.model, best_edge[0][0],
                                             self.statements)
                    v_stmt = _stmt_from_rule(self.model, best_edge[0][1],
                                             self.statements)
                    if u_stmt and v_stmt:
                        result['connect_stmts'] = (u_stmt, v_stmt)
                        logger.info("Model statements: %s" % str(self.statements))
                        logger.info("To explain %s, try connecting %s and %s" %
                                (self.explain, u_stmt, v_stmt))
        return result

    def suggest_statements(self, u_stmt, v_stmt, num_statements=5):
        def query_agent(ag):
            ns = None
            if 'HGNC' in ag.db_refs:
                (ns, id) = ('HGNC', ag.db_refs['HGNC'])
            elif 'FPLX' in ag.db_refs:
                (ns, id) = ('FPLX', ag.db_refs['FPLX'])
            elif 'CHEBI' in ag.db_refs:
                (ns, id) = ('CHEBI', ag.db_refs['CHEBI'])
            ag_str = ('%s@%s' % (id, ns)) if ns else None
            return ag_str
        subj = query_agent(u_stmt.agent_list()[1])
        obj = query_agent(v_stmt.agent_list()[0])
        if not (subj and obj):
            return []
        stmts = get_statements(subject=subj, object=obj, persist=False,
                               ev_limit=10, simple_response=True)
        stmts.sort(key=lambda s: len(s.evidence), reverse=True)
        end_ix = len(stmts) if len(stmts) < num_statements else num_statements
        return stmts[0:end_ix]
