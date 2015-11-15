from jnius import autoclass, cast
from TripsModule import trips_module

KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')

from bioagents.dtda import DTDA

class DTDA_Module(trips_module.TripsModule):
    def __init__(self, argv):
        super(DTDA_Module, self).__init__(argv)

    def init(self):
        super(DTDA_Module, self).init()
        self.send(KQMLPerformative.fromString(
            '(subscribe :content (request &key :content (hello . *)))'))
        self.ready()

    def receive_request(self, msg, content):
        content_list = cast(KQMLList, content)
        task = content_list.get(0).toString().lower()
        if task == 'is-drug-target':
            reply_content = self.respond_is_drug_target(content_list)
        elif task == 'find-target-drug':
            reply_content = self.respond_find_target_drug(content_list)
        elif task == 'find-disease-targets':
            reply_content = self.respond_find_disease_targets(content_list)
        elif task == 'find-treatment':
            reply_content = self.respond_find_treatment(content_list)
        else:
            self.error_reply(msg, 'unknown request task ' + task)
            return
    
        reply_msg = KQMLPerformative('tell')
        reply_msg.setParameter(':content', cast(KQMLObject, reply_content))
        self.reply(msg, reply_msg)
    
    def respond_is_drug_target(self, content_list):
        ddta = DTDA()
        # TODO: get parameters from content
        is_target = ddta.is_nominal_drug_target('Vemurafenib', 'BRAF')
        reply_content = KQMLList()
        if is_target:
            msg_str = 'TRUE'
        else:
            msg_str = 'FALSE'
        reply_content.add(msg_str)
        return reply_content
    
    def respond_find_target_drug(self, content_list):
        # TODO: implement
        reply_content = KQMLList()
        reply_content.add('')
        return reply_content
    
    def respond_find_disease_targets(self, content_list):
        # TODO: implement
        reply_content = KQMLList()
        reply_content.add('')
        return reply_content

    def respond_find_treatment(self, content_list):
        # TODO: implement
        reply_content = KQMLList()
        reply_content.add('')
        return reply_content



if __name__ == "__main__":
    import sys
    DTDA_Module(sys.argv[1:]).run()

