# MRA stands for mechanistic reasoning agent. 
# Its task is to use INDRA to construct mechanistic models of 
# biochemical systems from natural language, publications
# and databases.

from indra.pysb_assembler import PysbAssembler
from indra.statements import Agent
from indra.biopax import biopax_api
from indra.trips import trips_api
import copy

class MRA:
    def __init__(self):
        self.statements = []
        self.model = None
    
    def statement_exists(self, stmt):
        for s in self.statements:
            if stmt == s:
                return True
        return False

    def add_statements(self, stmts):
        for stmt in stmts:
            if not self.statement_exists(stmt):
                self.statements.append(stmt)

    def find_mechanism(self, source, target, force_contains):
        bp = biopax_api.process_pc_pathsfromto(source, target, neighbor_limit=1)
        return bp

    def build_model_from_text(self, model_txt):
        '''
        Build a model using INDRA from natural language.
        '''
        pa = PysbAssembler()
        tp = trips_api.process_text(model_txt)
        pa.add_statements(tp.statements)
        self.add_statements(tp.statements)
        self.model = pa.make_model()
        return self.model

    def replace_agent(self, agent_name, agent_replacement_names):
        '''
        Replace an agent in the stored statements with one or more 
        other agents. This is used, for instance, to expand a protein family
        to multiple specific proteins.
        '''
        for stmt in self.statements:
            agent = [k for k, v in stmt.__dict__.iteritems() if isinstance(v, Agent) and v.name == agent_name]
            if agent:
                self.statements.remove(stmt)
                for p in agent_replacement_names:
                    s = copy.deepcopy(stmt)
                    s.__dict__[agent[0]].name = p
                    self.add_statements([s])
        pa = PysbAssembler()
        pa.add_statements(self.statements)
        self.model = pa.make_model()
        return self.model

if __name__ == '__main__':
    mra = MRA()
    model = mra.build_model('EGF stimulation leads to the activity of HRAS')
     
    
