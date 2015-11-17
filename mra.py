# MRA stands for mechanistic reasoning agent. 
# Its task is to use INDRA to construct mechanistic models of 
# biochemical systems from natural language, publications
# and databases.

from indra.pysb_assembler import PysbAssembler
from indra.statements import Agent, Complex
from indra.biopax import biopax_api
from indra.trips import trips_api
from indra.databases import uniprot_client
from bioagents import nextprot_client
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

    def expand_model_from_text(self, model_txt):
        '''
        Expand a model using INDRA from natural language.
        '''
        pa = PysbAssembler()
        tp = trips_api.process_text(model_txt)
        self.add_statements(tp.statements)
        pa.add_statements(self.statements)
        self.model = pa.make_model()
        return self.model
    
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
            

    def replace_agent(self, agent_name, agent_replacement_names):
        '''
        Replace an agent in the stored statements with one or more 
        other agents. This is used, for instance, to expand a protein family
        to multiple specific proteins.
        '''
        for stmt in self.statements: 
            if isinstance(stmt, Complex):
                agent_key = [i for i, m in enumerate(stmt.members) if m.name == agent_name]
            else:
                agent_key = [k for k, v in stmt.__dict__.iteritems() if isinstance(v, Agent) and v.name == agent_name]
            if agent_key:
                self.statements.remove(stmt)
                for p in agent_replacement_names:
                    s = copy.deepcopy(stmt)
                    if isinstance(stmt, Complex):
                        s.members[agent_key[0]].name = p
                    else:
                        s.__dict__[agent_key[0]].name = p
                    self.add_statements([s])
        pa = PysbAssembler()
        pa.add_statements(self.statements)
        self.model = pa.make_model()
        return self.model

if __name__ == '__main__':
    mra = MRA()
    model = mra.build_model('EGF stimulation leads to the activity of HRAS')
     
    
