import sys
import argparse
import base64
import logging
from pysb import bng, Initial, Parameter, ComponentDuplicateNameError
from bioagents.trips import trips_module
from mea import MEA

from bioagents.trips.kqml_performative import KQMLPerformative
from bioagents.trips.kqml_list import KQMLList

logger = logging.getLogger('MEA')

class MEA_Module(trips_module.TripsModule):
    def __init__(self, argv):
        super(MEA_Module, self).__init__(argv)
        self.tasks = ['SIMULATE-MODEL']
        parser = argparse.ArgumentParser()
        parser.add_argument("--kappa_url", help="kappa endpoint")
        args = parser.parse_args()
        if args.kappa_url:
            self.kappa_url = args.kappa_url

    def init(self):
        '''
        Initialize TRIPS module
        '''
        super(MEA_Module, self).init()
        # Send subscribe messages
        for task in self.tasks:
            msg_txt =\
                '(subscribe :content (request &key :content (%s . *)))' % task
            self.send(KQMLPerformative.from_string(msg_txt))
        # Instantiate a singleton MEA agent
        self.mea = MEA()
        self.ready()

    def receive_request(self, msg, content):
        '''
        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        "tell" message is then sent back.
        '''
        content_list = content
        task_str = content_list[0].to_string().upper()
        if task_str == 'SIMULATE-MODEL':
            try:
                reply_content = self.respond_simulate_model(content_list)
            except Exception as e:
                self.error_reply(msg, 'Error in performing simulation task.')
        else:
            self.error_reply(msg, 'Unknown request task ' + task_str)
            return

        reply_msg = KQMLPerformative('reply')
        reply_msg.set_parameter(':content', reply_content)
        self.reply(msg, reply_msg)

    def respond_simulate_model(self, content_list):
        '''
        Response content to simulate-model request
        '''
        model_str = content_list.get_keyword_arg(':model')
        try:
            model_str = model_str.to_string()
            model = self.decode_model(model_str[1:-1])
        except InvalidModelDescriptionError:
            reply_content =\
                KQMLList.from_string('(FAILURE :reason INVALID_MODEL)')
            return reply_content
        target_entity = content_list.get_keyword_arg(':target_entity')
        if target_entity is not None:
            target_entity = target_entity.to_string()[1:-1]
        else:
            reply_content =\
                KQMLList.from_string('(FAILURE :reason MISSING_PARAMETER)')
            return reply_content
        target_pattern = content_list.get_keyword_arg(':target_pattern')
        if target_pattern is not None:
            target_pattern = target_pattern.to_string().lower()
        else:
            reply_content =\
                KQMLList.from_string('(FAILURE :reason MISSING_PARAMETER)')
            return reply_content
        condition_entity = content_list.get_keyword_arg(':condition_entity')
        if condition_entity is not None:
            condition_entity = condition_entity.to_string()[1:-1]
        condition_type = content_list.get_keyword_arg(':condition_type')
        if condition_type is not None:
            condition_type = condition_type.to_string().lower()

        self.get_context(model)
        if condition_entity is None:
            target_match = self.mea.check_pattern(model, target_entity,
                                                  target_pattern)
        else:
            target_match = self.mea.compare_conditions(model, target_entity,
                                                       target_pattern,
                                                       condition_entity,
                                                       condition_type)
        target_match_str = 'TRUE' if target_match else 'FALSE'
        reply_content = KQMLList()
        reply_content.add('SUCCESS :content (:target_match %s)' %
                          target_match_str)
        return reply_content

    @staticmethod
    def get_context(model):
        # TODO: Here we will have to query the context
        # for now it is hard coded
        kras = model.monomers['KRAS']
        try:
            p = Parameter('kras_act_0', 100)
            model.add_component(p)
            model.initial(kras(act='active'), p)
        except ComponentDuplicateNameError:
            model.parameters['kras_act_0'].value = 100

    @staticmethod
    def decode_model(model_enc_str):
        model_str = model_enc_str
        model = MEA_Module.model_from_string(model_str)
        return model

    @staticmethod
    def model_from_string(model_str):
        try:
            with open('tmp_model.py', 'wt') as fh:
                fh.write(model_str)
            # TODO: executing the model string is not safe
            # we should do this through a safer method
            exec model_str
        except Exception as e:
            raise InvalidModelDescriptionError
        logger.debug('\n\n')
        logger.debug('------BEGIN received model------')
        logger.debug('%s' % model_str)
        logger.debug('%s' % model.monomers)
        logger.debug('%s' % model.rules)
        logger.debug('%s' % model.parameters)
        logger.debug('%s' % model.initial_conditions)
        logger.debug('%s' % model.observables)
        logger.debug('-------END received model------')
        logger.debug('\n\n')
        return model

class InvalidModelDescriptionError(Exception):
    pass

if __name__ == "__main__":
    m = MEA_Module(['-name', 'MEA'] + sys.argv[1:]).run()
    m.start()
    m.join()
