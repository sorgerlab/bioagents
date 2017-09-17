import sys
import argparse
import logging
from pysb import bng, Initial, Parameter, ComponentDuplicateNameError
from mea import MEA

from kqml import KQMLModule, KQMLPerformative, KQMLList
from bioagents import Bioagent

logger = logging.getLogger('MEA')

class MEA_Module(Bioagent):
    name = 'MEA'
    tasks = ['SIMULATE-MODEL']
    def __init__(self, **kwargs):
        parser = argparse.ArgumentParser()
        parser.add_argument("--kappa_url", help="kappa endpoint")
        args = parser.parse_args()
        if args.kappa_url:
            self.kappa_url = args.kappa_url
        # Instantiate a singleton MEA agent
        self.mea = MEA()
        super(MEA_Module, self).__init__(**kwargs)

    def respond_simulate_model(self, content_list):
        '''
        Response content to simulate-model request
        '''
        model_str = content_list.get_keyword_arg(':model')
        try:
            #model_str = model_str.to_string()
            model = self.decode_model(model_str)
        except InvalidModelDescriptionError as e:
            logger.error(e)
            reply_content =\
                KQMLList.from_string('(FAILURE :reason INVALID_MODEL)')
            return reply_content
        except Exception as e:
            logger.error(e)
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
    def model_from_string(model_kqml_str):
        try:
            model_str = model_kqml_str.to_string()
            model_str = model_str[1:-1]
            with open('tmp_model.py', 'wt') as fh:
                fh.write(model_str)
            # TODO: executing the model string is not safe
            # we should do this through a safer method
            exec model_str
        except Exception as e:
            raise InvalidModelDescriptionError(e)
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
    MEA_Module(argv=sys.argv[1:])
