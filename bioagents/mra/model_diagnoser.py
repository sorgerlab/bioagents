from copy import deepcopy
from indra.mechlinker import MechLinker
from indra.statements import *

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
        pass
