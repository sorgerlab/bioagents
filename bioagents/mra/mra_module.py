import sys
import json
import random
import logging
from bioagents import Bioagent
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('MRA')
import pysb.export
from indra.statements import stmts_to_json
from indra.sources.trips.processor import TripsProcessor
from kqml import KQMLPerformative, KQMLList, KQMLString
from mra import MRA


class MRA_Module(Bioagent):
    name = "MRA"
    tasks = ['BUILD-MODEL', 'EXPAND-MODEL', 'MODEL-HAS-MECHANISM',
             'MODEL-REPLACE-MECHANISM', 'MODEL-REMOVE-MECHANISM',
             'MODEL-UNDO', 'MODEL-GET-UPSTREAM']
    def __init__(self, **kwargs):
        # Instantiate a singleton MRA agent
        self.mra = MRA()
        super(MRA_Module, self).__init__(**kwargs)

    def receive_tell(self, msg, content):
        tell_content = content.head().upper()
        if tell_content == 'START-CONVERSATION':
            logger.info('MRA resetting')

    def receive_request(self, msg, content):
        """Handle request messages and respond.

        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        message is then sent back.
        """
        ret = None
        try:
            ret = super(MRA_Module, self).receive_request(msg, content)
        except InvalidModelDescriptionError as e:
            logger.error('Invalid model description.')
            logger.error(e)
            reply_content = self.make_failure('INVALID_DESCRIPTION')
        except InvalidModelIdError as e:
            logger.error('Invalid model ID.')
            logger.error(e)
            reply_content = self.make_failure('INVALID_MODEL_ID')
        if ret is None:
            ret = self.reply_with_content(msg, reply_content)
        return ret

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
        model_msg = encode_indra_stmts(model)
        msg.sets('model', model_msg)
        # Add the diagrams
        diagrams = res.get('diagrams')
        if not no_display:
            if diagrams:
                rxn_diagram = diagrams.get('reactionnetwork')
                if rxn_diagram:
                    msg.sets('diagram', rxn_diagram)
                if not self.testing:
                    self.send_display_model(model_msg, diagrams)
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
                if not self.testing:
                    self.send_display_model(model_msg, diagrams)
        ambiguities = res.get('ambiguities')
        if ambiguities:
            ambiguities_msg = get_ambiguities_msg(ambiguities)
            msg.set('ambiguities', ambiguities_msg)
        return msg

    def respond_model_undo(self, content):
        """Return response content to model-undo request."""
        res = self.mra.model_undo()
        no_display = content.get('no-display')
        new_model_id = res.get('model_id')
        # Start a SUCCESS message
        msg = KQMLPerformative('SUCCESS')
        # Add the model id
        msg.set('model-id', str(new_model_id))
        # Add the INDRA model json
        model = res.get('model')
        model_msg = encode_indra_stmts(model)
        msg.sets('model', model_msg)
        action = content.get('action')
        actionl = KQMLList()
        if action['action'] == 'remove_stmts':
            actionl.append('remove_stmts')
            actionl.set('statements', encode_indra_stmts(action['stmts']))
        msg.set('action', actionl)

        # Add the diagram
        diagrams = res.get('diagrams')
        if not no_display:
            if diagrams:
                rxn_diagram = diagrams.get('reactionnetwork')
                if rxn_diagram:
                    msg.sets('diagram', rxn_diagram)
                if not self.testing:
                    self.send_display_model(model_msg, diagrams)
        return msg

    def respond_has_mechanism(self, content):
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

    def respond_remove_mechanism(self, content):
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
        # Add the removed statements
        removed = res.get('removed')
        if removed:
            removed_msg = encode_indra_stmts(removed)
            msg.sets('removed', removed_msg)
        # Add the diagram
        diagrams = res.get('diagrams')
        if not no_display:
            if diagrams:
                rxn_diagram = diagrams.get('reactionnetwork')
                if rxn_diagram:
                    msg.sets('diagram', rxn_diagram)
                if not self.testing:
                    self.send_display_model(model_msg, rxn_diagram)
        return msg

    def respond_model_get_upstream(self, content):
        """Return response content to model-upstream request."""
        target_arg = content.gets('target')
        target = get_target(target_arg)
        try:
            model_id = self._get_model_id(content)
        except Exception as e:
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

    def send_display_model(self, model, diagrams):
        msg = KQMLPerformative('tell')
        content = KQMLList('display-model')
        content.set('type', 'indra')
        content.sets('model', model)
        msg.set('content', content)
        self.send(msg)
        for diagram_type, path in diagrams.items():
            if not path:
                continue
            msg = KQMLPerformative('tell')
            content = KQMLList('display-image')
            content.set('type', diagram_type)
            content.sets('path', path)
            msg.set('content', content)
            self.send(msg)

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


class InvalidModelDescriptionError(Exception):
    pass


class InvalidModelIdError(Exception):
    pass


def ekb_from_agent(agent):
    dbids = ['%s:%s' % (k, v) for k, v in agent.db_refs.items()]
    dbids_str = '|'.join(dbids)
    termid = 'MRAGEN%d' % random.randint(1000001,10000000-1)
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
                             k, v in pr['refs'].items()])
        # TODO: once available, replace with real ont type
        pr_type = 'ONT::PROTEIN'
        s1 = '(term :ont-type %s :ids "%s" :name "%s")' % \
            (pr_type, pr_dbids, pr['name'])
        alt = ambiguity[0]['alternative']
        alt_dbids = '|'.join(['::'.join((k, v)) for
                              k, v in alt['refs'].items()])
        # TODO: once available, replace with real ont type
        alt_type = 'ONT::PROTEIN-FAMILY'
        s2 = '(term :ont-type %s :ids "%s" :name "%s")' % \
            (alt_type, alt_dbids, alt['name'])
        s = '(%s :preferred %s :alternative %s)' % \
            (term_id, s1, s2)
        sa.append(s)
    ambiguities_msg = KQMLList.from_string('(' + ' '.join(sa) + ')')
    return ambiguities_msg

if __name__ == "__main__":
    MRA_Module(argv=sys.argv[1:])

