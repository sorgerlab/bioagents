# MRA stands for mechanistic reasoning agent.
# Its task is to use INDRA to construct mechanistic models of
# biochemical systems from natural language, publications
# and databases.

import copy
from indra.assemblers import PysbAssembler
from indra.statements import Agent, Complex
from indra import trips
from indra.databases import uniprot_client
from bioagents.databases import nextprot_client

class MRA:
    def __init__(self):
        # This is a list of lists of Statements
        self.statements = []
        self.default_policy = 'two_step'

    def stmt_exists(self, stmts, stmt):
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

    def build_model_from_text(self, model_txt):
        '''
        Build a model using INDRA from natural language.
        '''
        tp = trips.process_text(model_txt)
        if tp is None:
            return None
        self.new_statements(tp.statements)
        pa = PysbAssembler(policies=self.default_policy)
        pa.add_statements(tp.statements)
        model = pa.make_model()
        return model

    def build_model_from_ekb(self, model_ekb):
        '''
        Build a model using DRUM extraction knowledge base.
        '''
        tp = trips.process_xml(model_ekb)
        if tp is None:
            return None
        self.new_statements(tp.statements)
        pa = PysbAssembler(policies=self.default_policy)
        pa.add_statements(tp.statements)
        model = pa.make_model()
        return model

    def expand_model_from_text(self, model_txt, model_id):
        '''
        Expand a model using INDRA from natural language.
        '''
        tp = trips.process_text(model_txt)
        self.extend_statements(tp.statements, model_id)
        pa = PysbAssembler(policies=self.default_policy)
        pa.add_statements(self.statements[model_id-1])
        model = pa.make_model()
        return model

    def expand_model_from_ekb(self, model_ekb, model_id):
        '''
        Expand a model using DRUM extraction knowledge base
        '''
        tp = trips.process_xml(model_ekb)
        self.extend_statements(tp.statements, model_id)
        pa = PysbAssembler(policies=self.default_policy)
        pa.add_statements(self.statements[model_id-1])
        model = pa.make_model()
        return model

    def find_family_members(self, family_name, family_id=None):
        '''
        Find specific members of a protein family. If only family_name is
        given then a Uniprot query is performed, if family_id is given then
        the information is taken from the corresponding database.
        '''
        if family_id is None:
            family_members = uniprot_client.get_family_members(family_name)
        elif family_id.startswith('FA'):
            nextprot_id = family_id[3:]
            family_members = nextprot_client.get_family_members(nextprot_id)
        else:
            return None
        return family_members

    def replace_agent(self, agent_name, agent_replacement_names, model_id):
        '''
        Replace an agent in the stored statements with one or more
        other agents. This is used, for instance, to expand a protein family
        to multiple specific proteins.
        '''
        for stmt in self.statements[model_id-1]:
            if isinstance(stmt, Complex):
                agent_key = [i for i, m in enumerate(stmt.members) if
                             m.name == agent_name]
            else:
                agent_key = [k for k, v in stmt.__dict__.iteritems() if
                             isinstance(v, Agent) and v.name == agent_name]
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
        return model

if __name__ == '__main__':
    mra = MRA()
    model = mra.build_model('EGF stimulation leads to the activity of HRAS')
