import logging
from copy import deepcopy
from indra.mechlinker import MechLinker
from indra.statements import *
from indra.explanation.model_checker import ModelChecker, stmts_for_path


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
        return result
