import os
import sys
import json
import random
import logging
from threading import Thread

import pysb.export

from indra.databases import hgnc_client
from indra.assemblers.english import EnglishAssembler
from indra.sources.trips.processor import TripsProcessor
from indra.preassembler.hierarchy_manager import hierarchies
from indra.statements import stmts_to_json, Complex, SelfModification,\
    ActiveForm
from indra import has_config

from kqml import KQMLPerformative, KQMLList, KQMLString

logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('MRA')

from bioagents import Bioagent, BioagentException
from .mra import MRA


if has_config('INDRA_DB_REST_URL') and has_config('INDRA_DB_REST_API_KEY'):
    from indra.sources.indra_db_rest import get_statements
    CAN_CHECK_STATEMENTS = True
else:
    logger.warning("Database web api not specified. Cannot get background.")
    CAN_CHECK_STATEMENTS = False


class MRA_Module(Bioagent):
    name = "MRA"
    tasks = ['BUILD-MODEL', 'EXPAND-MODEL', 'MODEL-HAS-MECHANISM',
             'MODEL-REPLACE-MECHANISM', 'MODEL-REMOVE-MECHANISM',
             'MODEL-UNDO', 'MODEL-GET-UPSTREAM', 'MODEL-GET-JSON',
             'USER-GOAL', 'DESCRIBE-MODEL']

    def __init__(self, **kwargs):
        # Instantiate a singleton MRA agent
        self.mra = MRA()
        super(MRA_Module, self).__init__(**kwargs)
        self.have_explanation = False

    def receive_request(self, msg, content):
        """Handle request messages and respond.

        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        message is then sent back.
        """
        try:
            super(MRA_Module, self).receive_request(msg, content)
            return
        except InvalidModelDescriptionError as e:
            logger.error('Invalid model description.')
            logger.error(e)
            reply_content = self.make_failure('INVALID_DESCRIPTION')
        except InvalidModelIdError as e:
            logger.error('Invalid model ID.')
            logger.error(e)
            reply_content = self.make_failure('INVALID_MODEL_ID')
        self.reply_with_content(msg, reply_content)
        return

    def respond_build_model(self, content):
        """Return response content to build-model request."""
        descr = content.gets('description')
        descr_format = content.gets('format')
        no_display = content.get('no-display')
        if not descr_format or descr_format == 'ekb':
            res = self.mra.build_model_from_ekb(descr)
        elif descr_format == 'indra_json':
            res = self.mra.build_model_from_json(descr)
        else:
            err_msg = 'Invalid description format: %s' % descr_format
            raise InvalidModelDescriptionError(err_msg)
        if res.get('error'):
            raise InvalidModelDescriptionError(res.get('error'))
        model_id = res.get('model_id')
        if model_id is None:
            raise InvalidModelDescriptionError()
        # Start a SUCCESS message
        msg = KQMLPerformative('SUCCESS')
        # Add the model id
        msg.set('model-id', str(model_id))
        # Add the INDRA model json
        model = res.get('model')
        if model and (descr_format == 'ekb' or not descr_format):
            self.send_background_support(model)
        model_msg = encode_indra_stmts(model)
        msg.sets('model', model_msg)
        # Add the diagrams
        diagrams = res.get('diagrams')
        if not no_display:
            if diagrams:
                rxn_diagram = diagrams.get('reactionnetwork')
                if rxn_diagram:
                    msg.sets('diagram', rxn_diagram)
                self.send_display_model(diagrams)

        # Indicate whether the goal has been explained
        has_expl = res.get('has_explanation')
        if has_expl is not None:
            msg.set('has_explanation', str(has_expl).upper())

        # Send out various model diagnosis messages
        self.send_model_diagnoses(res)

        # Once we sent out the diagnosis messages, we make sure we keep
        # track of whether we have an explanation
        if has_expl:
            self.have_explanation = True

        # Analyze the model for issues
        # Report ambiguities
        ambiguities = res.get('ambiguities')
        if ambiguities:
            ambiguities_msg = get_ambiguities_msg(ambiguities)
            msg.set('ambiguities', ambiguities_msg)
        return msg

    def respond_expand_model(self, content):
        """Return response content to expand-model request."""
        descr = content.gets('description')
        model_id = self._get_model_id(content)
        descr_format = content.gets('format')
        no_display = content.get('no-display')
        try:
            if not descr_format or descr_format == 'ekb':
                res = self.mra.expand_model_from_ekb(descr, model_id)
            elif descr_format == 'indra_json':
                res = self.mra.expand_model_from_json(descr, model_id)
            else:
                err_msg = 'Invalid description format: %s' % descr_format
                raise InvalidModelDescriptionError(err_msg)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        new_model_id = res.get('model_id')
        if new_model_id is None:
            raise InvalidModelDescriptionError()
        # Start a SUCCESS message
        msg = KQMLPerformative('SUCCESS')
        # Add the model id
        msg.set('model-id', str(new_model_id))
        # Add the INDRA model json
        model = res.get('model')
        model_msg = encode_indra_stmts(model)
        msg.sets('model', model_msg)
        # Add the INDRA model new json
        model_new = res.get('model_new')

        # Indicate whether the goal has been explained
        has_expl = res.get('has_explanation')
        if has_expl is not None:
            msg.set('has_explanation', str(has_expl).upper())

        # Send out various model diagnosis messages
        self.send_model_diagnoses(res)

        # Once we sent out the diagnosis messages, we make sure we keep
        # track of whether we have an explanation
        if has_expl:
            self.have_explanation = True

        if model_new and (descr_format == 'ekb' or not descr_format):
            self.send_background_support(model_new)
        if model_new:
            model_new_msg = encode_indra_stmts(model_new)
            msg.sets('model-new', model_new_msg)
        # Add the diagram
        if not no_display:
            diagrams = res.get('diagrams')
            if diagrams:
                rxn_diagram = diagrams.get('reactionnetwork')
                if rxn_diagram:
                    msg.sets('diagram', rxn_diagram)
                self.send_display_model(diagrams)
        # Analyze the model for issues

        # Report ambiguities
        ambiguities = res.get('ambiguities')
        if ambiguities:
            ambiguities_msg = get_ambiguities_msg(ambiguities)
            msg.set('ambiguities', ambiguities_msg)
        return msg

    def respond_model_undo(self, content):
        """Return response content to model-undo request."""
        res = self.mra.model_undo()
        no_display = content.get('no-display')
        model_id = res.get('model_id')
        # Start a SUCCESS message
        msg = KQMLPerformative('SUCCESS')
        # Add the model id
        msg.set('model-id', 'NIL' if model_id is None else str(model_id))
        # Add the INDRA model json
        model = res.get('model')

        # Handle empty model
        if not model:
            self.send_clean_model()

        model_msg = encode_indra_stmts(model)
        msg.sets('model', model_msg)
        # Get the action and add it to the message
        action = res.get('action')
        actionl = KQMLList()
        if action['action'] == 'remove_stmts':
            actionl.append('remove_stmts')
            actionl.sets(
                'statements',
                encode_indra_stmts(action['statements'])
                )
        msg.set('action', actionl)

        # Add the diagram
        diagrams = res.get('diagrams')
        if not no_display:
            if diagrams:
                rxn_diagram = diagrams.get('reactionnetwork')
                if rxn_diagram:
                    msg.sets('diagram', rxn_diagram)
                self.send_display_model(diagrams)
        return msg

    def respond_model_has_mechanism(self, content):
        """Return response content to model-has-mechanism request."""
        ekb = content.gets('description')
        model_id = self._get_model_id(content)
        try:
            res = self.mra.has_mechanism(ekb, model_id)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        # Start a SUCCESS message
        msg = KQMLPerformative('SUCCESS')
        # Add the model id
        msg.set('model-id', str(model_id))
        # Add TRUE or FALSE for has-mechanism
        has_mechanism_msg = 'TRUE' if res['has_mechanism'] else 'FALSE'
        msg.set('has-mechanism', has_mechanism_msg)
        query = res.get('query')
        if query:
            query_msg = encode_indra_stmts([query])
            msg.sets('query', query_msg)
        return msg

    def respond_model_remove_mechanism(self, content):
        """Return response content to model-remove-mechanism request."""
        ekb = content.gets('description')
        model_id = self._get_model_id(content)
        no_display = content.get('no-display')
        try:
            res = self.mra.remove_mechanism(ekb, model_id)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
        model_id = res.get('model_id')
        if model_id is None:
            raise InvalidModelDescriptionError('Could not find model id.')
        # Start a SUCCESS message
        msg = KQMLPerformative('SUCCESS')
        # Add the model id
        msg.set('model-id', str(model_id))
        # Add the INDRA model json
        model = res.get('model')
        model_msg = encode_indra_stmts(model)
        msg.sets('model', model_msg)

        # Handle empty model
        if not model:
            self.send_clean_model()

        # Get the action and add it to the message
        removed = res.get('removed')
        if not removed:
            msg = self.make_failure('REMOVE_FAILED')
            return msg
        else:
            actionl = KQMLList('remove_stmts')
            actionl.sets('statements', encode_indra_stmts(removed))
            msg.set('action', actionl)

        # Add the diagram
        diagrams = res.get('diagrams')
        logger.info(diagrams)
        if not no_display:
            if diagrams:
                rxn_diagram = diagrams.get('reactionnetwork')
                if rxn_diagram:
                    msg.sets('diagram', rxn_diagram)
                self.send_display_model(diagrams)
        return msg

    def respond_model_get_upstream(self, content):
        """Return response content to model-upstream request."""
        target_arg = content.gets('target')
        target = get_target(target_arg)
        try:
            model_id = self._get_model_id(content)
        except Exception:
            model_id = 1
        upstream = self.mra.get_upstream(target, model_id)
        terms = []
        names = []
        for agent in upstream:
            term = ekb_from_agent(agent)
            if term is not None:
                names.append(KQMLString(agent.name))
                terms.append(KQMLString(term))
        reply = KQMLList('SUCCESS')
        reply.set('upstream', KQMLList(terms))
        reply.set('upstream-names', KQMLList(names))
        return reply

    def respond_model_get_json(self, content):
        """Return response content to model-get-json request."""
        try:
            model_id = self._get_model_id(content)
        except Exception:
            model_id = None
        model = self.mra.get_model_by_id(model_id)
        if model is not None:
            model_msg = encode_indra_stmts(model)
            reply = KQMLList('SUCCESS')
            reply.sets('model', model_msg)
        else:
            reply = self.make_failure('MISSING_MODEL')
        return reply

    def respond_user_goal(self, content):
        """Record user goal and return success if possible"""
        explain = content.gets('explain')
        self.mra.set_user_goal(explain)
        # We reset the explanations here
        self.have_explanation = False
        reply = KQMLList('SUCCESS')
        return reply

    def respond_describe_model(self, content):
        """Convert the model to natural language."""
        # Get the model.
        model_id = self._get_model_id(content)
        model = self.mra.get_model_by_id(model_id)

        # Turn the model into a text description.
        english_assembler = EnglishAssembler(model)
        desc = english_assembler.make_model()

        # Respond to the BA.
        resp = KQMLList('SUCCESS')
        resp.sets('description', desc)
        return resp

    def send_model_diagnoses(self, res):
        # SUGGESTIONS
        # If there is an explanation, english assemble it
        expl_path = res.get('explanation_path')
        if expl_path:
            # Only send this if we haven't already sent an explanation
            if not self.have_explanation:
                ea_path = EnglishAssembler(expl_path)
                path_str = ea_path.make_model()
                ea_goal = EnglishAssembler([self.mra.explain])
                goal_str = ea_goal.make_model()
                if path_str and goal_str:
                    explanation_str = (
                            'Our model can now explain how %s: <i>%s</i>' %
                            (goal_str[:-1], path_str))
                    content = KQMLList('SPOKEN')
                    content.sets('WHAT', explanation_str)
                    self.tell(content)

        # If there is a suggestion, say it
        suggs = res.get('stmt_suggestions')
        if suggs:
            say = 'I have some suggestions on how to complete our model.'
            say += ' We could try modeling one of:<br>'
            stmt_str = '<ul>%s</ul>' % \
                       ''.join([('<li>%s</li>' % EnglishAssembler([stmt]).make_model())
                                for stmt in suggs])
            say += stmt_str
            content = KQMLList('SPOKEN')
            content.sets('WHAT', say)
            self.tell(content)

        # If there are corrections
        corrs = res.get('stmt_corrections')
        if corrs:
            stmt = corrs[0]
            say = 'It looks like a required activity is missing,'
            say += ' consider revising to <i>%s</i>' % \
                   (EnglishAssembler([stmt]).make_model())
            content = KQMLList('SPOKEN')
            content.sets('WHAT', say)
            self.tell(content)

    def send_display_model(self, diagrams):
        for diagram_type, resource in diagrams.items():
            if not resource:
                continue
            if diagram_type == 'sbgn':
                content = KQMLList('display-sbgn')
                content.set('type', diagram_type)
                content.sets('graph', resource)
            else:
                content = KQMLList('display-image')
                content.set('type', diagram_type)
                content.sets('path', resource)
            self.tell(content)

    def send_clean_model(self):
        msg = KQMLPerformative('request')
        content = KQMLList('clean-model')
        msg.set('content', content)
        self.send(msg)

    def send_background_support(self, stmts):
        logger.info('Sending support for %d statements' % len(stmts))

        def send_support():
            for_what = 'the mechanism you added'
            for stmt in stmts:
                try:
                    matched = _get_matching_stmts(stmt)
                    logger.info("Found %d statements supporting %s"
                                % (len(matched), stmt))
                except BioagentException as e:
                    logger.error("Got exception while looking for support for "
                                 "%s" % stmt)
                    logger.exception(e)
                    self.send_null_provenance(stmt, for_what,
                                              'due to an internal error')
                    continue
                if matched:
                    self.send_provenance_for_stmts(matched, for_what)
                else:
                    self.send_null_provenance(stmt, for_what)

        th = Thread(target=send_support)
        th.start()
        th.join(2)
        return

    def _get_model_id(self, content):
        model_id_arg = content.get('model-id')
        if model_id_arg is None:
            logger.error('Model ID missing.')
            raise InvalidModelIdError
        try:
            model_id_str = model_id_arg.to_string()
            model_id = int(model_id_str)
        except Exception as e:
            logger.error('Could not get model ID as integer.')
            raise InvalidModelIdError(e)
        if not self.mra.has_id(model_id):
            logger.error('Model ID does not refer to an existing model.')
            raise InvalidModelIdError
        return model_id


class InvalidModelDescriptionError(BioagentException):
    pass


class InvalidModelIdError(BioagentException):
    pass


def ekb_from_agent(agent):
    dbids = ['%s:%s' % (k, v) for k, v in agent.db_refs.items()]
    dbids_str = '|'.join(dbids)
    termid = 'MRAGEN%d' % random.randint(1000001, 10000000-1)
    open_tag = '<ekb><TERM dbid="%s" id="%s">' % (dbids_str, termid)
    type_tag = '<type>ONT::GENE-PROTEIN</type>'
    name_tag = '<name>%s</name>' % agent.name
    hgnc_id = agent.db_refs.get('HGNC')
    # TODO: handle non-genes here
    if not hgnc_id:
        return None
    drum_terms = '<drum-terms><drum-term dbid="HGNC:%s" ' % hgnc_id + \
        'match-score="1.0" matched-name="%s" ' % agent.name + \
        'name="%s"></drum-term></drum-terms>' % agent.name
    text_tag = '<text>%s</text>' % agent.db_refs.get('TEXT')
    close_tag = '</TERM></ekb>'
    ekb = ' '.join([open_tag, type_tag, name_tag, drum_terms,
                    text_tag, close_tag])
    return ekb


def get_target(target_str):
    tp = TripsProcessor(target_str)
    terms = tp.tree.findall('TERM')
    assert len(terms) > 0, "No terms found."
    term_id = terms[0].attrib['id']
    agent = tp._get_agent_by_id(term_id, None)
    return agent


def encode_pysb_model(pysb_model):
    model_str = pysb.export.export(pysb_model, 'pysb_flat')
    model_str = str(model_str.strip())
    return model_str


def encode_indra_stmts(stmts):
    stmts_json = stmts_to_json(stmts)
    json_str = json.dumps(stmts_json)
    return json_str


def get_ambiguities_msg(ambiguities):
    sa = []
    for term_id, ambiguity in ambiguities.items():
        pr = ambiguity[0]['preferred']
        pr_dbids = '|'.join(['::'.join((k, v)) for
                             k, v in sorted(pr['refs'].items(),
                                            key=lambda x: x[0])])
        # TODO: once available, replace with real ont type
        pr_type = 'ONT::PROTEIN'
        s1 = '(term :ont-type %s :ids "%s" :name "%s")' % \
            (pr_type, pr_dbids, pr['name'])
        alt = ambiguity[0]['alternative']
        alt_dbids = '|'.join(['::'.join((k, v)) for
                              k, v in sorted(alt['refs'].items(),
                                             key=lambda x: x[0])])
        # TODO: once available, replace with real ont type
        alt_type = 'ONT::PROTEIN-FAMILY'
        s2 = '(term :ont-type %s :ids "%s" :name "%s")' % \
            (alt_type, alt_dbids, alt['name'])
        s = '(%s :preferred %s :alternative %s)' % \
            (term_id, s1, s2)
        sa.append(s)
    ambiguities_msg = KQMLList.from_string('(' + ' '.join(sa) + ')')
    return ambiguities_msg


def _get_agent_comp(agent):
    eh = hierarchies['entity']
    a_ns, a_id = agent.get_grounding()
    if (a_ns is None) or (a_id is None):
        return None
    uri = eh.get_uri(a_ns, a_id)
    comp_id = eh.components.get(uri)
    return comp_id


def _get_agent_ref(agent):
    """Get the preferred ref for an agent for db web api."""
    if agent is None:
        return None
    ag_hgnc_id = hgnc_client.get_hgnc_id(agent.name)
    if ag_hgnc_id is not None:
        return ag_hgnc_id + "@HGNC"
    db_refs = agent.db_refs
    for namespace in ['HGNC', 'FPLX', 'CHEBI', 'TEXT']:
        if namespace in db_refs.keys():
            return '%s@%s' % (db_refs[namespace], namespace)
    return '%s@%s' % (agent.name, 'TEXT')


def _get_matching_stmts(stmt_ref):
    if not CAN_CHECK_STATEMENTS:
        return []
    # Filter by statement type.
    stmt_type = stmt_ref.__class__.__name__
    agent_name_list = [_get_agent_ref(ag) for ag in stmt_ref.agent_list()]
    non_binary_statements = [Complex, SelfModification, ActiveForm]
    # TODO: We should look at more than just the agent name.
    # Doing so efficiently may require changes to the web api.
    kwargs = {}
    if any([isinstance(stmt_ref, tp) for tp in non_binary_statements]):
        kwargs['agents'] = [ag_name for ag_name in agent_name_list
                            if ag_name is not None]
    else:
        kwargs = {k: v for k, v in zip(['subject', 'object'], agent_name_list)}
        if not any(kwargs.values()):
            raise BioagentException('Either subject or object must be '
                                    'something other than None.')
    kwargs['ev_limit'] = 2
    kwargs['persist'] = False
    return get_statements(stmt_type=stmt_type, **kwargs)


_resource_dir = os.path.dirname(os.path.realpath(__file__)) + '/../resources/'

if __name__ == "__main__":
    MRA_Module(argv=sys.argv[1:])
