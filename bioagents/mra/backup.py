# MRA stands for mechanistic reasoning agent.
# Its task is to use INDRA to construct mechanistic models of
# biochemical systems from natural language, publications
# and databases.

import os
import sys
import copy
import json
import logging
import networkx
import subprocess
import kappy
from indra.sources import trips
from indra.statements import Complex, Activation, IncreaseAmount, \
                            AddModification, stmts_from_json
from indra.databases import uniprot_client
from indra.preassembler.hierarchy_manager import hierarchies
from indra.assemblers import pysb_assembler, PysbAssembler
from pysb.bng import BngInterfaceError
from pysb.tools import render_reactions
from pysb.export import export
from indra.util.kappa_util import im_json_to_graph, cm_json_to_graph


logger = logging.getLogger('MRA')


class MRA(object):
    def __init__(self):
        self.models = {}
        self.transformations = []
        self.id_counter = 0
        self.default_policy = 'one_step'
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
        ambiguities = get_ambiguities(tp)
        res['ambiguities'] = ambiguities
        model_exec = self.assemble_pysb(stmts)
        res['model_exec'] = model_exec
        res['diagrams'] = make_diagrams(model_exec, model_id,
                                        self.models[model_id])
        return res

    def build_model_from_json(self, model_json):
        """Build a model using INDRA JSON."""
        stmts = stmts_from_json(json.loads(model_json))
        model_id = self.new_model(stmts)
        res = {'model_id': model_id,
               'model': stmts}
        if not stmts:
            return res
        model_exec = self.assemble_pysb(stmts)
        res['model_exec'] = model_exec
        res['diagrams'] = make_diagrams(model_exec, model_id,
                                        self.models[model_id])
        return res

    def expand_model_from_ekb(self, model_ekb, model_id):
        """Expand a model using DRUM extraction knowledge base."""
        tp = trips.process_xml(model_ekb)
        if tp is None:
            return {'error': 'Failed to process EKB.'}
        stmts = tp.statements
        new_model_id, new_stmts = self.extend_model(stmts, model_id)
        logger.info('Old model id: %s, New model id: %s' %
                    (model_id, new_model_id))
        model_stmts = self.models[new_model_id]
        res = {'model_id': new_model_id,
               'model': model_stmts}
        if not model_stmts:
            return res
        ambiguities = get_ambiguities(tp)
        res['ambiguities'] = ambiguities
        res['model_new'] = new_stmts
        model_exec = self.assemble_pysb(model_stmts)
        res['model_exec'] = model_exec
        res['diagrams'] = make_diagrams(model_exec, new_model_id)
        return res

    def expand_model_from_json(self, model_json, model_id):
        """Expand a model using INDRA JSON."""
        stmts = stmts_from_json(json.loads(model_json))
        new_model_id, new_stmts = self.extend_model(stmts, model_id)
        logger.info('Old model id: %s, New model id: %s' %
                    (model_id, new_model_id))
        model_stmts = self.models[new_model_id]
        res = {'model_id': new_model_id,
               'model': model_stmts}
        if not model_stmts:
            return res
        res['model_new'] = new_stmts
        model_exec = self.assemble_pysb(model_stmts)
        res['model_exec'] = model_exec
        res['diagrams'] = make_diagrams(model_exec, new_model_id)
        return res

    def has_mechanism(self, mech_ekb, model_id):
        """Return True if the given model contains the given mechanism."""
        tp = trips.process_xml(mech_ekb)
        res = {}
        if not tp.statements:
            res['has_mechanism'] = False
            return res
        query_st = tp.statements[0]
        res['query'] = query_st
        model_stmts = self.models[model_id]
        for model_st in model_stmts:
            if model_st.refinement_of(query_st, hierarchies):
                res['has_mechanism'] = True
                return res
        res['has_mechanism'] = False
        return res

    def remove_mechanism(self, mech_ekb, model_id):
        """Return a new model with the given mechanism having been removed."""
        tp = trips.process_xml(mech_ekb)
        rem_stmts = tp.statements
        new_stmts = []
        removed_stmts = []
        model_stmts = self.models[model_id]
        for model_st in model_stmts:
            found = False
            for rem_st in rem_stmts:
                if model_st.refinement_of(rem_st, hierarchies):
                    found = True
                    break
            if not found:
                new_stmts.append(model_st)
            else:
                removed_stmts.append(model_st)
        res = {'model_id': model_id,
               'model': new_stmts}
        model_exec = self.assemble_pysb(new_stmts)
        res['model_exec'] = model_exec
        if removed_stmts:
            res['removed'] = removed_stmts
        res['diagrams'] = make_diagrams(model_exec, model_id)
        self.new_model(new_stmts)
        return res

    def model_undo(self):
        """Revert to the previous model version."""
        forward_action = self.transformations.pop()
        if forward_action[0] == 'add_stmts':
            stmts_added = forward_action[1]
            old_model_id = forward_action[2]
            new_model_id = self.get_new_id()
            stmts = self.models[old_model_id] \
                if old_model_id is not None else []
            self.models[new_model_id] = stmts
            undo_action = {'action': 'remove_stmts', 'statements': stmts_added}
        res = {'model_id': new_model_id,
               'model': stmts,
               'action': undo_action}
        model_exec = self.assemble_pysb(stmts)
        if not stmts:
            return res
        res['ambiguities'] = []
        res['diagrams'] = make_diagrams(model_exec, new_model_id,
                                        self.models[new_model_id])
        return res

    def get_upstream(self, target, model_id):
        """Get upstream agents in model."""
        stmts = self.models[model_id]
        rel_stmts = [st for st in stmts if isinstance(st, IncreaseAmount) or
                                           isinstance(st, Activation)]
        rel_stmts = [st for st in rel_stmts if st.subj and
                     (st.obj.name == target.name)]
        upstream_agents = [st.subj for st in rel_stmts]
        return upstream_agents

    def new_model(self, stmts):
        model_id = self.get_new_id()
        self.models[model_id] = stmts
        self.transformations.append(('add_stmts', stmts, None, model_id))
        return model_id

    def extend_model(self, stmts, model_id):
        old_stmts = self.models[model_id]
        new_model_id = self.get_new_id()
        self.models[new_model_id] = [st for st in self.models[model_id]]
        new_stmts = []
        for st in stmts:
            if not stmt_exists(self.models[model_id], st):
                self.models[new_model_id].append(st)
                new_stmts.append(st)
        self.transformations.append(('add_stmts', new_stmts, model_id,
                                     new_model_id))
        return new_model_id, new_stmts

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


def get_ambiguities(tp):
    terms = tp.tree.findall('TERM')
    all_ambiguities = {}
    for term in terms:
        term_id = term.attrib.get('id')
        _, _, ambiguities = trips.processor._get_db_refs(term)
        if ambiguities:
            all_ambiguities[term_id] = ambiguities
    return all_ambiguities


def make_diagrams(pysb_model, model_id, indra_model):
    sbgn = make_sbgn(pysb_model, model_id)
    rxn = draw_reaction_network(pysb_model, model_id)
    cm = draw_contact_map(pysb_model, model_id)
    im = draw_influence_map(pysb_model, model_id, indra_model)
    diagrams = {'reactionnetwork': rxn, 'contactmap': cm,
                'influencemap': im, 'sbgn': sbgn}
    return diagrams


def make_sbgn(pysb_model, model_id):
    pa = PysbAssembler()
    pa.model = pysb_model
    for m in pysb_model.monomers:
        pysb_assembler.set_extended_initial_condition(pysb_model, m, 0)
    try:
        sbgn_str = pa.export_model('sbgn')
    except BngInterfaceError:
        logger.error('Reaction network could not be generated for SBGN.')
        return None
    return sbgn_str


def draw_influence_map(pysb_model, model_id, indra_model):
    """Generate a Kappa influence map, draw it and save it as a PNG."""
    try:
        im = make_influence_map(pysb_model)
        im = make_influence_map_labels_natural_language(im, pysb_model,
                                                        indra_model)
        fname = 'model%d_im' % model_id
        abs_path = os.path.abspath(os.getcwd())
        full_path = os.path.join(abs_path, fname + '.png')
        im_agraph = networkx.nx_agraph.to_agraph(im)
        im_agraph.draw(full_path, prog='dot')
    except Exception as e:
        logger.exception('Could not draw influence map for model.')
        logger.exception(e)
        return None
    return full_path


def make_influence_map(pysb_model):
    """Return a Kappa influence map."""
    kappa = kappy.KappaStd()
    model_str = export(pysb_model, 'kappa')
    kappa.add_model_string(model_str)
    kappa.project_parse()
    imap = kappa.analyses_influence_map()
    im = im_json_to_graph(imap)
    for param in pysb_model.parameters:
        try:
            im.remove_node(param.name)
        except:
            pass
    return im


def make_influence_map_labels_natural_language(im, pysb_model, indra_model):
    """Replaces the labels of the influence map with natural language labels.
    """
    # import ipdb;ipdb.set_trace()

    # Get the name of all the rules in the pysb model
    rule_names = [rule.name for rule in pysb_model.rules]


    for annotation in pysb_model.annotations:
        if annotation.subject in rule_names:
            name = annotation.subject
            if annotation.predicate == 'from_indra_statement':
                # We found the INDRA statement uuid corresponding to a rule
                statement_uuid = annotation.object
            sys.stdout.flush()
    return im


def draw_contact_map(pysb_model, model_id):
    try:
        cm = make_contact_map(pysb_model)
        fname = 'model%d_cm' % model_id
        abs_path = os.path.abspath(os.getcwd())
        full_path = os.path.join(abs_path, fname + '.png')
        cm.draw(full_path, prog='dot')
    except Exception as e:
        logger.exception('Could not draw contact map for model.')
        logger.exception(e)
        return None
    return full_path


def make_contact_map(pysb_model):
    """Return a Kappa contact map."""
    kappa = kappy.KappaStd()
    model_str = export(pysb_model, 'kappa')
    kappa.add_model_string(model_str)
    kappa.project_parse()
    cmap = kappa.analyses_contact_map()
    cm = cm_json_to_graph(cmap)
    return cm


def draw_reaction_network(pysb_model, model_id):
    """Generate a PySB/BNG reaction network as a PNG file."""
    try:
        for m in pysb_model.monomers:
            pysb_assembler.set_extended_initial_condition(pysb_model, m, 0)
        fname = 'model%d_rxn' % model_id
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
