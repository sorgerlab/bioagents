import sys
import json
import random
import logging
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('MRA')
import pysb.export
from indra.statements import stmts_to_json
from indra.trips.processor import TripsProcessor
from kqml import *
from mra import MRA


class MRA_Module(KQMLModule):
    def __init__(self, argv, testing=False):
        # Instantiate a singleton MRA agent
        self.mra = MRA()
        self.testing = testing
        if testing:
            return
        super(MRA_Module, self).__init__(argv)
        self.tasks = ['BUILD-MODEL', 'EXPAND-MODEL', 'MODEL-HAS-MECHANISM',
                      'MODEL-REPLACE-MECHANISM', 'MODEL-REMOVE-MECHANISM',
                      'MODEL-UNDO', 'MODEL-GET-UPSTREAM']
        for task in self.tasks:
            msg_txt = \
                '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.from_string(msg_txt))
        self.ready()
        super(MRA_Module, self).start()

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
        try:
            content = msg.get('content')
            task_str = content.head().upper()
        except Exception as e:
            logger.error('Could not get task string from request.')
            logger.error(e)
            self.error_reply(msg, 'Invalid task')
        try:
            if task_str == 'BUILD-MODEL':
                reply_content = self.respond_build_model(content)
            elif task_str == 'EXPAND-MODEL':
                reply_content = self.respond_expand_model(content)
            elif task_str == 'MODEL-UNDO':
                reply_content = self.respond_model_undo(content)
            elif task_str == 'MODEL-HAS-MECHANISM':
                reply_content = self.respond_has_mechanism(content)
            elif task_str == 'MODEL-REMOVE-MECHANISM':
                reply_content = self.respond_remove_mechanism(content)
            elif task_str == 'MODEL-GET-UPSTREAM':
                reply_content = self.respond_model_get_upstream(content)
            else:
                self.error_reply(msg, 'Unknown task ' + task_str)
                return
        except InvalidModelDescriptionError as e:
            logger.error('Invalid model description.')
            logger.error(e)
            reply_content = make_failure('INVALID_DESCRIPTION')
        except InvalidModelIdError as e:
            logger.error('Invalid model ID.')
            logger.error(e)
            reply_content = make_failure('INVALID_MODEL_ID')
        reply_msg = KQMLPerformative('reply')
        reply_msg.set('content', reply_content)
        self.reply(msg, reply_msg)

    def respond_build_model(self, content):
        """Return response content to build-model request."""
        ekb = content.gets('description')
        try:
            res = self.mra.build_model_from_ekb(ekb)
        except Exception as e:
            raise InvalidModelDescriptionError(e)
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
        rxn_diagram = diagrams.get('rxn')
        if rxn_diagram:
            msg.sets('diagram', rxn_diagram)
        else:
            msg.sets('diagram', '')
        ambiguities = res.get('ambiguities')
        if ambiguities:
            ambiguities_msg = get_ambiguities_msg(ambiguities)
            msg.set('ambiguities', ambiguities_msg)
        if not self.testing:
            self.send_display_model(model_msg, diagrams)
        return msg

    def respond_expand_model(self, content):
        """Return response content to expand-model request."""
        ekb = content.gets('description')
        model_id = self._get_model_id(content)
        try:
            res = self.mra.expand_model_from_ekb(ekb, model_id)
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
        diagrams = res.get('diagrams')
        rxn_diagram = diagrams.get('rxn')
        if rxn_diagram:
            msg.sets('diagram', rxn_diagram)
        else:
            msg.sets('diagram', '')
        ambiguities = res.get('ambiguities')
        if ambiguities:
            ambiguities_msg = get_ambiguities_msg(ambiguities)
            msg.set('ambiguities', ambiguities_msg)
        if not self.testing:
            self.send_display_model(model_msg, diagrams)
        return msg

    def respond_model_undo(self, content):
        """Return response content to model-undo request."""
        res = self.mra.model_undo()
        new_model_id = res.get('model_id')
        # Start a SUCCESS message
        msg = KQMLPerformative('SUCCESS')
        # Add the model id
        msg.set('model-id', str(new_model_id))
        # Add the INDRA model json
        model = res.get('model')
        model_msg = encode_indra_stmts(model)
        msg.sets('model', model_msg)
        # Add the diagram
        diagrams = res.get('diagrams')
        rxn_diagram = diagrams.get('rxn')
        if rxn_diagram:
            msg.sets('diagram', rxn_diagram)
        else:
            msg.sets('diagram', '')
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
        rxn_diagram = diagrams.get('rxn')
        if rxn_diagrams:
            msg.sets('diagram', rxn_diagram)
        else:
            msg.sets('diagram', '')
        if not self.testing:
            self.send_display_model(model_msg, diagram)
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
    open_tag = '<TERM dbid="%s" id="%s">' % (dbids_str, termid)
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
    close_tag = '</TERM>'
    ekb = ' '.join([open_tag, type_tag, name_tag, drum_terms,
                    text_tag, close_tag])
    return ekb

def get_target(target_str):
    target_str = '<ekb>' + target_str + '</ekb>'
    tp = TripsProcessor(target_str)
    terms = tp.tree.findall('TERM')
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

def make_failure(reason):
    msg = KQMLList('FAILURE')
    msg.set('reason', reason)
    return msg

if __name__ == "__main__":
    MRA_Module(['-name', 'MRA'] + sys.argv[1:])
