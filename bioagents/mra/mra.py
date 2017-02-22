# MRA stands for mechanistic reasoning agent.
# Its task is to use INDRA to construct mechanistic models of
# biochemical systems from natural language, publications
# and databases.

import os
import copy
import logging
import subprocess
from indra import trips
from indra.statements import Complex
from indra.databases import uniprot_client
from indra.preassembler.hierarchy_manager import hierarchies
from indra.assemblers import pysb_assembler, PysbAssembler, EnglishAssembler
from pysb.tools import render_reactions
from bioagents.databases import nextprot_client

logger = logging.getLogger('MRA')

class MRA(object):
    def __init__(self):
        self.models = {}
        self.id_counter = 0
        self.default_policy = 'two_step'
        self.default_initial_amount = 100.0

    def get_new_id(self):
        self.id_counter += 1
        return self.id_counter

    def has_id(self, model_id):
        if model_id in self.models:
            return True
        return False

    def assemble_pysb(self, stmts):
        pa = PysbAssembler(policies=self.default_policy)
        pa.add_statements(stmts)
        pa.make_model()
        pa.add_default_initial_conditions(self.default_initial_amount)
        return pa.model

    def assemble_english(self, stmts):
        ea = EnglishAssembler(stmts)
        txt = ea.make_model()
        return txt

    def build_model_from_ekb(self, model_ekb):
        """Build a model using DRUM extraction knowledge base."""
        tp = trips.process_xml(model_ekb)
        if tp is None:
            return {'error': 'Failed to process EKB.'}

        stmts = tp.statements
        model_id = self.new_model(stmts)
        res = {'model_id': model_id,
               'model': stmts}
        if not stmts:
            return res
        model_nl = self.assemble_english(stmts)
        res['model_nl'] = model_nl
        model_exec = self.assemble_pysb(stmts)
        res['model_exec'] = model_exec
        diagram = make_model_diagram(model_exec, model_id)
        if diagram:
            res['diagram'] = diagram
        return res

    def expand_model_from_ekb(self, model_ekb, model_id):
        """Expand a model using DRUM extraction knowledge base."""
        tp = trips.process_xml(model_ekb)
        self.extend_statements(tp.statements, model_id)
        pa = PysbAssembler(policies=self.default_policy)
        pa.add_statements(self.models[model_id-1])
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

    def new_model(self, stmts):
        model_id = self.get_new_id()
        self.models[model_id] = stmts
        return model_id

    def extend_statements(self, stmts, to_model_id):
        old_stmts = self.models[to_model_id]
        new_model_id = self.get_new_id()
        self.statements[new_model_id] = (self.statements[old_model_id])
        for st in stmts:
            if not stmt_exists(self.statements[model_id], st):
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


def make_model_diagram(pysb_model, model_id):
    """Generate a PySB/BNG reaction network as a PNG file."""
    try:
        for m in pysb_model.monomers:
            pysb_assembler.set_extended_initial_condition(pysb_model, m, 0)
        fname = 'model%d' % model_id
        diagram_dot = render_reactions.run(pysb_model)
    # TODO: use specific PySB/BNG exceptions and handle them
    # here to show meaningful error messages
    except Exception as e:
        logger.error('Could not generate model diagram.')
        logger.error(e)
        return None
    try:
        with open(fname + '.dot', 'wt') as fh:
            fh.write(diagram_dot)
        subprocess.call(('dot -T png -o %s.png %s.dot' %
                         (fname, fname)).split(' '))
        abs_path = os.path.abspath(os.getcwd())
        full_path = os.path.join(abs_path, fname + '.png')
    except Exception as e:
        logger.error('Could not save model diagram.')
        logger.error(e)
        return None
    return full_path


def stmt_exists(stmts, stmt):
    for st1 in stmts:
        if st1.matches(stmt):
            return True
    return False
