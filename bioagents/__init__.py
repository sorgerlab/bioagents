import logging
from kqml import KQMLModule, KQMLPerformative
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)

class Bioagent(KQMLModule):
    """Abstract class for bioagents."""
    name = "Generic Bioagent (Should probably be overwritten)"
    tasks = []
    def __init__(self, **kwargs):
        super(Bioagent, self).__init__(name = self.name, **kwargs)
        for task in self.tasks:
            self.subscribe_request(task)
        
        self.ready()
        self.start()
        return
    
    def reply_with_content(self, msg, reply_content):
        "A wrapper around the reply method from KQMLModule."
        if not self.testing:
            reply_msg = KQMLPerformative('reply')
            reply_msg.set('content', reply_content)
            self.reply(msg, reply_msg)
            ret = None
        else:
            ret = (msg, reply_content)
        return ret
    
    def error_reply(self, msg, comment):
        if not self.testing:
            return KQMLModule.error_reply(self, msg, comment)
        else:
            return (msg, comment)