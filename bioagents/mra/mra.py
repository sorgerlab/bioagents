# MRA stands for mechanistic reasoning agent.
# Its task is to use INDRA to construct mechanistic models of
# biochemical systems from natural language, publications
# and databases.

import copy
from indra.assemblers import PysbAssembler
from indra.statements import Complex
from indra import trips
from indra.databases import uniprot_client
from bioagents.databases import nextprot_client
from indra.preassembler.hierarchy_manager import hierarchies


class MRA(object):
    def __init__(self):
        # This is a list of lists of Statements
        self.statements = []
        self.default_policy = 'two_step'
        self.default_initial_amount = 100.0

    def build_model_from_ekb(self, model_ekb):
        """Build a model using DRUM extraction knowledge base."""
        tp = trips.process_xml(model_ekb)
        if tp is None:
            return None
        self.new_statements(tp.statements)
        pa = PysbAssembler(policies=self.default_policy)
        pa.add_statements(tp.statements)
        model = pa.make_model()
        pa.add_default_initial_conditions(self.default_initial_amount)
        return model

    def has_mechanism(self, mech_ekb, model_id):
        """Return True if the given model contains the given mechanism."""
        tp = trips.process_xml(mech_ekb)
        if not tp.statements:
            return False
        query_st = tp.statements[0]
        model_stmts = self.statements[model_id-1]
        for model_st in model_stmts:
            if model_st.refinement_of(query_st, hierarchies):
                return True
        return False

    def remove_mechanism(self, mech_ekb, model_id):
        """Return a new model with the given mechanism having been removed."""
        tp = trips.process_xml(mech_ekb)
        model_stmts = self.statements[model_id-1]
        new_stmts = []
        for model_st in model_stmts:
            found = False
            for rem_st in tp.statements:
                if model_st.refinement_of(rem_st, hierarchies):
                    found = True
                    break
            if not found:
                new_stmts.append(model_st)
        self.new_statements(new_stmts)
        pa = PysbAssembler(policies=self.default_policy)
        pa.add_statements(new_stmts)
        model = pa.make_model()
        return model

    def model_undo(self):
        """Revert to the previous model version."""
        if len(self.statements) > 1:
            model = self.statements[model_id-2]
            self.statements.append(model)
        elif len(self.statements) == 1:
            model = []
            self.statements.append(model)
        else:
            model = None
        return model

    def expand_model_from_ekb(self, model_ekb, model_id):
        """Expand a model using DRUM extraction knowledge base."""
        tp = trips.process_xml(model_ekb)
        self.extend_statements(tp.statements, model_id)
        pa = PysbAssembler(policies=self.default_policy)
        pa.add_statements(self.statements[model_id-1])
        model = pa.make_model()
        pa.add_default_initial_conditions(self.default_initial_amount)
        return model

    @staticmethod
    def stmt_exists(stmts, stmt):
        for st1 in stmts:
            if st1.matches(stmt):
                return True
        return False

    def new_statements(self, stmts):
        self.statements.append(stmts)

    def extend_statements(self, stmts, model_id):
        self.statements.append(self.statements[model_id-1])
        for st in stmts:
            if not self.stmt_exists(self.statements[model_id], st):
                self.statements[model_id].append(st)

    @staticmethod
    def find_family_members(family_name, family_id=None):
        """Find specific members of a protein family.

        If only family_name is given then a Uniprot query is
        performed, if family_id is given then the information is taken
        from the corresponding database.
        """
        if family_id is None:
            family_members = uniprot_client.get_family_members(family_name)
        elif family_id.startswith('FA'):
            nextprot_id = family_id[3:]
            family_members = nextprot_client.get_family_members(nextprot_id)
        else:
            return None
        return family_members

    def replace_agent(self, agent_name, agent_replacement_names, model_id):
        """Replace an agent in a model with other agents.

        This is used, for instance, to expand a protein family to
        multiple specific proteins.
        """
        for stmt in self.statements[model_id-1]:
            agent_key = [i for i, m in enumerate(stmt.agent_list())
                         if m is not None and m.name == agent_name]
            if agent_key:
                self.statements[model_id-1].remove(stmt)
                for p in agent_replacement_names:
                    s = copy.deepcopy(stmt)
                    if isinstance(stmt, Complex):
                        s.members[agent_key[0]].name = p
                    else:
                        s.__dict__[agent_key[0]].name = p
                    self.extend_statements([s], model_id)
        pa = PysbAssembler()
        pa.add_statements(self.statements[model_id-1])
        model = pa.make_model()
        pa.add_default_initial_conditions(self.default_initial_amount)
        return model
