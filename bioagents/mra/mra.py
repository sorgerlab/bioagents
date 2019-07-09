# MRA stands for mechanistic reasoning agent.
# Its task is to use INDRA to construct mechanistic models of
# biochemical systems from natural language, publications
# and databases.

import os
import copy
import json
import logging
import networkx
import subprocess
from datetime import datetime

import kappy

from bioagents import get_img_path
from indra.sources import trips
from indra.statements import Complex, Activation, IncreaseAmount, \
    stmts_from_json
from indra.preassembler.hierarchy_manager import hierarchies
from indra.assemblers.pysb import assembler as pysb_assembler
from indra.assemblers.pysb import PysbAssembler
from pysb.bng import BngInterfaceError
from pysb.tools import render_reactions

from pysb.export import export
from indra.assemblers.pysb.kappa_util import im_json_to_graph, cm_json_to_graph
from bioagents.mra.sbgn_colorizer import SbgnColorizer
from bioagents.mra.model_diagnoser import ModelDiagnoser
logger = logging.getLogger('MRA')


class MRA(object):
    def __init__(self):
        self.models = {}
        self.transformations = []
        self.id_counter = 0
        self.default_policy = 'one_step'
        self.default_initial_amount = 100.0
        self.explain = None
        self.context = None

    def get_new_id(self):
        self.id_counter += 1
        return self.id_counter

    def has_id(self, model_id):
        if model_id in self.models:
            return True
        return False

    def assemble_pysb(self, stmts):
        pa = PysbAssembler()
        pa.add_statements(stmts)
        pa.make_model(policies=self.default_policy)
        pa.add_default_initial_conditions(self.default_initial_amount)
        return pa.model

    # BUILD / EXPAND / REMOVE / UNDO

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
                                        self.models[model_id], self.context)
        self.run_diagnoser(res, stmts, model_exec)
        return res

    def build_model_from_json(self, model_json):
        """Build a model using INDRA JSON."""
        stmts = stmts_from_json(json.loads(model_json))
        return self.build_model_from_stmts(stmts)

    def build_model_from_stmts(self, stmts):
        model_id = self.new_model(stmts)
        res = {'model_id': model_id,
               'model': stmts}
        if not stmts:
            return res
        model_exec = self.assemble_pysb(stmts)
        res['model_exec'] = model_exec
        res['diagrams'] = make_diagrams(model_exec, model_id,
                                        self.models[model_id], self.context)
        self.run_diagnoser(res, stmts, model_exec)
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
        res['diagrams'] = make_diagrams(model_exec, new_model_id,
                                        self.models[new_model_id],
                                        self.context)
        self.run_diagnoser(res, model_stmts, model_exec)
        return res

    def expand_model_from_json(self, model_json, model_id):
        """Expand a model using INDRA JSON."""
        stmts = stmts_from_json(json.loads(model_json))
        return self.expand_model_from_stmts(stmts, model_id)

    def expand_model_from_stmts(self, stmts, model_id):
        """Expand a model using INDRA JSON."""
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
        res['diagrams'] = make_diagrams(model_exec, new_model_id,
                                        self.models[new_model_id],
                                        self.context)
        self.run_diagnoser(res, model_stmts, model_exec)
        return res

    def extend_model(self, new_stmts, model_id):
        # Lists to keep track of types of statements by their
        # relation compared to the old set of statements
        old_stmts = self.models[model_id]
        stmts_old_to_propagate = []
        stmts_old_matched = []
        stmts_old_refined = []
        stmts_old_refinement = []
        stmts_new_to_add = []
        stmts_new_refined = []
        stmts_new_matched = []
        # Look at each old statement and determine the relationship
        # of each new statement with respect to it
        for ost in old_stmts:
            for nst in new_stmts:
                # The old and the new statements are exact matches
                # We propagate the old one
                if ost.matches(nst):
                    if ost not in stmts_old_matched:
                        stmts_old_matched.append(ost)
                    if nst not in stmts_new_matched:
                        stmts_new_matched.append(nst)
                # The old statement is a refinement of the new one
                # We propagate the old one
                elif ost.refinement_of(nst, hierarchies):
                    if ost not in stmts_old_refinement:
                        stmts_old_refinement.append(ost)
                    if nst not in stmts_new_refined:
                        stmts_new_refined.append(nst)
                # The new statement is a refinement of the old one
                # We add the new statement and don't propagate the old one
                elif nst.refinement_of(ost, hierarchies):
                    if ost not in stmts_old_refined:
                        stmts_old_refined.append(ost)
                    if nst not in stmts_new_to_add:
                        stmts_new_to_add.append(nst)
                # Otherwise there is no relation so the old statement
                # won't be added to any of the lists above for this
                # new statement
            # Unless the old statement is refined, it is propagated
            if ost not in stmts_old_refined:
                stmts_old_to_propagate.append(ost)

        # Add any new Statement that has not already been added
        # or is not matched or refined by an old statement
        for nst in new_stmts:
            if nst not in stmts_new_refined + stmts_new_matched + \
                    stmts_new_to_add:
                stmts_new_to_add.append(nst)

        logger.debug('Statements to propagate: %s' % stmts_old_to_propagate)
        logger.debug('Statements to add: %s' % stmts_new_to_add)
        new_model_id = self.get_new_id()
        self.models[new_model_id] = stmts_old_to_propagate + stmts_new_to_add
        # FIXME: Would undo-s work after a refinement?
        self.transformations.append(('add_stmts', stmts_new_to_add, model_id,
                                     new_model_id))
        return new_model_id, stmts_new_to_add

    def remove_mechanism(self, mech_ekb, model_id):
        """Return a new model with the given mechanism having been removed."""
        tp = trips.process_xml(mech_ekb)
        rem_stmts = tp.statements
        return self.remove_mechanism_from_stmts(rem_stmts, model_id)

    def remove_mechanism_from_stmts(self, rem_stmts, model_id):
        logger.info('Removing statements: %s' % rem_stmts)

        model_stmts = self.models[model_id]
        # Statements that are matched in the model and will be removed
        stmts_old_to_remove = []
        # Statements to be removed that are matched in the model
        stmts_rem_matched = []
        for ost in model_stmts:
            for rst in rem_stmts:
                if ost.refinement_of(rst, hierarchies):
                    if ost not in stmts_old_to_remove:
                        stmts_old_to_remove.append(ost)
                    if rst not in stmts_rem_matched:
                        stmts_rem_matched.append(rst)
        # Statements that to be removed that didn't have any matching
        # Statements in the model
        stmts_rem_unmatched = [st for st in rem_stmts if st not in
                               stmts_rem_matched]
        # Statements in the model that weren't matched by and to-remove
        # Statements and therefore remain in the model.
        stmts_old_propagate = [st for st in model_stmts if st not in
                               stmts_old_to_remove]
        # Make a new model ID
        # FIXME: this should result in a proper remove transformation added
        #  to the set of transformations.
        new_model_id = self.new_model(stmts_old_propagate)
        model_exec = self.assemble_pysb(self.models[new_model_id])
        res = {'model_id': new_model_id, 'model': self.models[new_model_id],
               'model_exec': model_exec}
        if stmts_old_to_remove:
            res['removed'] = stmts_old_to_remove
        if stmts_rem_unmatched:
            res['remove_unmatched'] = stmts_rem_unmatched
        if self.models[new_model_id]:
            res['diagrams'] = make_diagrams(model_exec, new_model_id,
                                            self.models[new_model_id],
                                            self.context)
        return res

    def model_undo(self):
        """Revert to the previous model version."""
        # Figure out what the last forward action was, if any
        forward_action = self.transformations.pop() if self.transformations \
            else None
        # Handle the case that there are no previous transformations (left).
        if not forward_action:
            return {'model_id': None, 'model': [],
                    'action': {'action': 'no_op', 'statements': [],
                               'reason': 'NO_ACTIONS'}}
        # Or we got an action that we don't know how to undo
        elif forward_action[0] != 'add_stmts':
            new_model_id = self.id_counter
            stmts = self.models[self.id_counter] \
                if self.id_counter else []
            undo_action = {'action': 'no_op', 'statements': [],
                           'reason': 'UNKNOWN_ACTION'}
        # Otherwise we are undoing an add_stmts forward action and have to
        # remove the corresponding statements
        else:
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
                                        self.models[new_model_id],
                                        self.context)
        return res

    def new_model(self, stmts):
        model_id = self.get_new_id()
        self.models[model_id] = stmts
        self.transformations.append(('add_stmts', stmts, None, model_id))
        return model_id

    # MODEL DIAGNOSIS

    def run_diagnoser(self, res, model_stmts, model_exec):
        # Use a model diagnoser to identify explanations given the executable
        # model, the current statements, and the explanation goal
        if self.explain:
            md = ModelDiagnoser(model_stmts, model=model_exec,
                                explain=self.explain)
            md_result = md.check_explanation()
            res.update(md_result)
            # If we got a proposal for a statement, get a specific
            # recommendation
            connect_stmts = res.get('connect_stmts')
            if connect_stmts:
                u_stmt, v_stmt = connect_stmts
                stmt_suggestions, sugg_subj, sugg_obj = \
                    md.suggest_statements(u_stmt, v_stmt)
                if stmt_suggestions:
                    agents = [a.name for a in stmt_suggestions[0].agent_list()
                              if a is not None]
                    if len(set(agents)) > 1:
                        res['stmt_suggestions'] = stmt_suggestions
                        res['stmt_suggestions_subj'] = sugg_subj
                        res['stmt_suggestions_obj'] = sugg_obj
        md = ModelDiagnoser(model_stmts)
        acts = md.get_missing_activities()
        if acts:
            logger.info('Missing activities found: %s' % acts)
            res['stmt_corrections'] = acts

    def has_mechanism(self, mech_json, model_id):
        """Return True if the given model contains the given mechanism."""
        stmts = stmts_from_json(json.loads(mech_json))
        res = {}
        if not stmts:
            res['has_mechanism'] = False
            return res
        query_st = stmts[0]
        res['query'] = query_st
        model_stmts = self.models[model_id]
        for model_st in model_stmts:
            if model_st.refinement_of(query_st, hierarchies):
                res['has_mechanism'] = True
                return res
        res['has_mechanism'] = False
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

    def set_user_goal(self, explain):
        # Get the event itself
        tp = trips.process_xml(explain)
        if tp is None:
            return {'error': 'Failed to process EKB.'}
        print(tp.statements)
        if not tp.statements:
            return
        self.explain = tp.statements[0]

        # Look for a term representing a cell line
        def get_context(explain_xml):
            import xml.etree.ElementTree as ET
            et = ET.fromstring(explain_xml)
            cl_tag = et.find("TERM/[type='ONT::CELL-LINE']/text")
            if cl_tag is not None:
                cell_line = cl_tag.text
                cell_line.replace('-', '')
                return cell_line
            return None
        try:
            self.context = get_context(explain)
        except Exception as e:
            logger.error('MRA could not set context from USER-GOAL')
            logger.error(e)

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

    def get_model_by_id(self, model_id=None):
        """Return model given the ID or the latest if None."""
        if model_id is None:
            model_id = self.id_counter
        try:
            model = self.models[model_id]
        except KeyError:
            return None
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


def make_diagrams(pysb_model, model_id, current_model, context=None):
    sbgn = make_sbgn(pysb_model, model_id)
    if sbgn is not None:
        sbgn = sbgn.encode('utf-8')
        if context:
            try:
                cell_line = ccle_map[context]
            except KeyError:
                logger.info('Could not find profile info for %s cell line' %
                            context)
                cell_line = 'A375_SKIN'
        else:
            cell_line = 'A375_SKIN'
        try:
            logger.info('Coloring SBGN to %s cell line.' % cell_line)
            colorizer = SbgnColorizer(sbgn)
            colorizer.set_style_expression_mutation(current_model,
                                                    cell_line=cell_line)
            sbgn = colorizer.generate_xml()
        except Exception as e:
            logger.error('Could not set SBGN colors')
            logger.error(e)

    rxn = draw_reaction_network(pysb_model, model_id)
    cm = draw_contact_map(pysb_model, model_id)
    im = draw_influence_map(pysb_model, model_id)
    diagrams = {'reactionnetwork': rxn, 'contactmap': cm,
                'influencemap': im, 'sbgn': sbgn}
    return diagrams


def make_pic_name(model_id, token):
    """Create a standardized picture name."""
    s = 'model%d_%s' % (model_id, token)
    return get_img_path(s)


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


def draw_influence_map(pysb_model, model_id):
    """Generate a Kappa influence map, draw it and save it as a PNG."""
    try:
        im = make_influence_map(pysb_model)
        fname = make_pic_name(model_id, 'im') + '.png'
        im_agraph = networkx.nx_agraph.to_agraph(im)
        im_agraph.draw(fname, prog='dot')
    except Exception as e:
        logger.exception('Could not draw influence map for model.')
        logger.exception(e)
        return None
    return fname


def make_influence_map(pysb_model):
    """Return a Kappa influence map."""
    pa = PysbAssembler()
    pa.model = pysb_model
    im = pa.export_model('kappa_im')
    return im


def draw_contact_map(pysb_model, model_id):
    try:
        cm = make_contact_map(pysb_model)
        fname = make_pic_name(model_id, 'cm') + '.png'
        cm.draw(fname, prog='dot')
    except Exception as e:
        logger.exception('Could not draw contact map for model.')
        logger.exception(e)
        return None
    return fname


def make_contact_map(pysb_model):
    """Return a Kappa contact map."""
    pa = PysbAssembler()
    pa.model = pysb_model
    cm = pa.export_model('kappa_cm')
    return cm


def draw_reaction_network(pysb_model, model_id):
    """Generate a PySB/BNG reaction network as a PNG file."""
    try:
        for m in pysb_model.monomers:
            pysb_assembler.set_extended_initial_condition(pysb_model, m, 0)
        diagram_dot = render_reactions.run(pysb_model)
    # TODO: use specific PySB/BNG exceptions and handle them
    # here to show meaningful error messages
    except Exception as e:
        logger.error('Could not generate model diagram.')
        logger.error(e)
        return None
    try:
        fname_prefix = make_pic_name(model_id, 'rxn')
        with open(fname_prefix + '.dot', 'wt') as fh:
            fh.write(diagram_dot)
        subprocess.call(('dot -T png -o %s.png %s.dot' %
                         (fname_prefix, fname_prefix)).split(' '))
        fname = fname_prefix + '.png'
    except Exception as e:
        logger.error('Could not save model diagram.')
        logger.error(e)
        return None
    return fname


def make_ccle_map():
    fname = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '../resources/ccle_lines.txt')
    with open(fname, 'r') as fh:
        clines = [l.strip() for l in fh.readlines()]

    ccle_map = {c.split('_')[0]: c for c in clines}
    return ccle_map


ccle_map = make_ccle_map()
