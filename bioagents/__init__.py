import sys
import logging
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
from kqml import KQMLModule, KQMLPerformative, KQMLList

class Bioagent(KQMLModule):
    """Abstract class for bioagents."""
    name = "Generic Bioagent (Should probably be overwritten)"
    tasks = []
    def __init__(self, **kwargs):
        super(Bioagent, self).__init__(name=self.name, **kwargs)
        for task in self.tasks:
            self.subscribe_request(task)

        self.ready()
        self.start()
        return

    def receive_request(self, msg, content):
        """Handle request messages and respond.

        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply
        message is then sent back.
        """
        try:
            content = msg.get('content')
            task = content.head().upper()
        except Exception as e:
            self.logger.error('Could not get task string from request.')
            self.logger.error(e)
            reply_content = self.make_failure('INVALID_REQUEST')

        if task in self.tasks:
            reply_content = self._respond_to(task, content)
        else:
            self.logger.error('Could not perform task.')
            self.logger.error("Task %s not found in %s." %
                              (task, str(self.tasks)))
            reply_content = self.make_failure('UNKNOWN_TASK')

        return self.reply_with_content(msg, reply_content)

    def _respond_to(self, task, content):
        """Get the method to responsd to the task indicated by task."""
        resp_name = "respond_" + task.replace('-', '_').lower()
        try:
            resp = getattr(self, resp_name)
        except AttributeError:
            self.logger.error("Tried to execute unimplemented task.")
            self.logger.error("Did not find response method %s." % resp_name)
            return self.make_failure('INVALID_TASK')
        try:
            reply_content = resp(content)
            return reply_content
        except Exception as e:
            # This line below is needed to make sure a more specific exception
            # from the child class is raised
            # raise e, None, sys.exc_info()[2]
            # However this would mean that exceptions unhandled in the child
            # class would actually error here. Currently if receive_request
            # is reimplemented in the child class, the Exception here is
            # always the one triggered, and the (more meaningful) child
            # exception is ignored.
            self.logger.error('Could not perform response to %s' % task)
            self.logger.error(e)
            return self.make_failure('INTERNAL_FAILURE')

    def reply_with_content(self, msg, reply_content):
        """A wrapper around the reply method from KQMLModule."""
        if not self.testing:
            reply_msg = KQMLPerformative('reply')
            reply_msg.set('content', reply_content)
            self.reply(msg, reply_msg)
        return (msg, reply_content)

    def error_reply(self, msg, comment):
        if not self.testing:
            return KQMLModule.error_reply(self, msg, comment)
        else:
            return (msg, comment)

    def make_failure(self, reason=None):
        msg = KQMLList('FAILURE')
        if reason:
            msg.set('reason', reason)
        return msg
