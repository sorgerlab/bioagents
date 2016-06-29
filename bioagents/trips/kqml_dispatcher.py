import logging

class KQMLDispatcher(object):
    def __init__(self, rec, inp, agent_name):
        super(KQMLDispatcher, self).__init__()
        self.receiver = rec
        self.reader = inp
        self.reply_continuations = {}
        self.counter = 0
        self.name = 'KQML-Dispatcher-%d' % self.counter
        self.agent_name = agent_name
        self.logger = logging.getLogger(agent_name)
        self.counter += 1
        self.shutdown_initiated = False

    def start(self):
        try:
            while True:
                msg = self.reader.read_performative()
                self.dispatch_message(msg)
        # FIXME: not handling KQMLException and
        # KQMLBadCharacterException
        except KeyboardInterrupt:
            self.receiver.receive_eof()
        except EOFError:
            self.receiver.receive_eof()
        except IOError as ex:
            if not self.shutdown_initiated:
                self.receiver.handle_exception(ex)

    def warn(self, msg):
        logger.warning(msg)

    def shutdown(self):
        self.shutdown_initiated = True
        try:
            # FIXME: print thread info instead of blank quotes
            self.logger.error('KQML dispatcher shutdown: ' + '' +
                              ': closing reader')
            self.reader.close()
            # FIXME: print thread info instead of blank quotes
            self.logger.error('KQML dispatcher shutdown: ' + '' +
                              ': done')
        except IOError:
            logger.error('KQML dispatched IOError.')
            pass

    def dispatch_message(self, msg):
        verb = msg.get_verb()
        if verb is None:
            self.receiver.receive_message_missing_verb(msg)
            return
        reply_id_obj = msg.get_parameter(':in-reply-to')
        if reply_id_obj is not None:
            reply_id = reply_id_obj.string_value().upper()
            try:
                value = self.reply_continuations[reply_id]
                value.receive(msg)
                self.reply_continuations.pop(reply_id, 0)
                return
            except KeyError:
                pass

        vl = verb.lower()
        content = msg.get_parameter(':content')
        content_msg_types = ['ask-if','ask-all','ask-one','stream-all','tell', 
                            'untell', 'deny', 'insert', 'uninsert', 
                            'delete-one', 'delete-all', 'undelete', 'achieve', 
                            'unachieve', 'advertise', 'subscribe', 'standby', 
                            'register', 'forward', 'broadcast', 
                            'transport-address', 'broker-one', 'broker-all',
                            'recommend-one', 'recommend-all', 'recruit-one',
                            'recruit-all', 'reply', 'request', 'tell']
        if vl in content_msg_types and content is None:
            self.receiver.receive_message_missing_content(msg)
            return
        if vl == 'ask-if':
            self.receiver.receive_ask_if(msg, content)
        elif vl == 'ask-all':
            self.receiver.receive_ask_all(msg, content)
        elif vl == 'ask-one':
            self.receiver.receive_ask_one(msg, content)
        elif vl == 'stream-all':
            self.receiver.receive_stream_all(msg, content)
        elif vl == 'tell':
            self.receiver.receive_tell(msg, content)
        elif vl == 'untell':
            self.receiver.receive_untell(msg, content)
        elif vl == 'deny':
            self.receiver.receive_deny(msg, content)
        elif vl == 'insert':
            self.receiver.receive_insert(msg, content)
        elif vl == 'uninsert':
            self.receiver.receive_uninsert(msg, content)
        elif vl == 'delete-one':
            self.receiver.receive_delete_one(msg, content)
        elif vl == 'delete-all':
            self.receiver.receive_delete_all(msg, content)
        elif vl == 'undelete':
            self.receiver.receive_undelete(msg, content)
        elif vl == 'achieve':
            self.receiver.receive_achieve(msg, content)
        elif vl == 'unachieve':
            self.receiver.receive_unachieve(msg, content)
        elif vl == 'advertise':
            self.receiver.receive_advertise(msg, content)
        elif vl == 'subscribe':
            self.receiver.receive_subscribe(msg, content)
        elif vl == 'standby':
            self.receiver.receive_standby(msg, content)
        elif vl == 'register':
            self.receiver.receive_register(msg, content)
        elif vl == 'forward':
            self.receiver.receive_forward(msg, content)
        elif vl == 'broadcast':
            self.receiver.receive_broadcast(msg, content)
        elif vl == 'transport-address':
            self.receiver.receive_transport_address(msg, content)
        elif vl == 'broker-one':
            self.receiver.receive_broker_one(msg, content)
        elif vl == 'broker-all':
            self.receiver.receive_broker_all(msg, content)
        elif vl == 'recommend-one':
            self.receiver.receive_recommend_one(msg, content)
        elif vl == 'recommend-all':
            self.receiver.receive_recommend_all(msg, content)
        elif vl == 'recruit-one':
            self.receiver.receive_recruit_one(msg, content)
        elif vl == 'recruit-all':
            self.receiver.receive_recruit_all(msg, content)
        elif vl == 'reply':
            self.receiver.receive_reply(msg, content)
        elif vl == 'request':
            self.receiver.receive_request(msg, content)
        elif vl == 'eos':
            self.receiver.receive_eos(msg)
        elif vl == 'error':
            self.receiver.receive_error(msg)
        elif vl == 'sorry':
            self.receiver.receive_sorry(msg)
        elif vl == 'ready':
            self.receiver.receive_ready(msg)
        elif vl == 'next':
            self.receiver.receive_next(msg)
        elif vl == 'rest':
            self.receiver.receive_rest(msg)
        elif vl == 'discard':
            self.receiver.receive_discard(msg)
        elif vl == 'unregister':
            self.receiver.receive_unregister(msg)
        else:
            self.receiver.receive_other_performative(msg)

    def add_reply_continuation(self, reply_id, cont):
        self.reply_continuations[reply_id.upper()] = cont
