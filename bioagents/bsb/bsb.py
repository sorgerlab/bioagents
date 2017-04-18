import sys
import time
import json
import uuid
import random
import select
import socket
import logging
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('BSB')
from socketIO_client import SocketIO

from indra.assemblers import SBGNAssembler

from kqml import *


def dummy(arg1):
    print(arg1)

def get_example_model():
    from indra.statements import Phosphorylation, Agent
    st = Phosphorylation(Agent('MAP2K1'), Agent('MAPK1'), 'T', '185')
    return [st]

class BSB(object):
    def __init__(self,  bob_port=6200, sbgnviz_port=3000):
        self.user_name = 'BOB'

        self.bob_port = bob_port
        self.sbgnviz_port = sbgnviz_port

        # Startup sequences
        self.bob_startup()
        self.sbgn_startup()

    def start(self):
        logger.info('Starting...')
        # Wait for things to happen
        socks = [self.socket_b, self.socket_s._transport._connection.sock]
        while True:
            try:
                ready_socks, _, _ = select.select(socks, [], [])
                for sock in ready_socks:
                    if sock == self.socket_s._transport._connection.sock:
                        self.socket_s.wait(seconds=0.1)
                    else:
                        data, addr = sock.recvfrom(4086)
                        if data:
                            self.on_bob_message(data)
            except KeyboardInterrupt:
                break
        self.socket_s.emit('disconnect')
        self.socket_s.disconnect()

    def bob_startup(self):
        logger.info('Initializing Bob connection...')
        self.bob_uttnum = 1
        self.socket_b = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_b.connect(('localhost', self.bob_port))
        msg = '(register :name bsb)'
        self.socket_b.sendall(msg)
        msg = '(subscribe :content (tell &key :content (spoken . *)))'
        self.socket_b.sendall(msg)
        msg = '(subscribe :content (request &key :content (display-model . *)))'
        self.socket_b.sendall(msg)
        msg = '(tell :content (module-status ready))'
        self.socket_b.sendall(msg)

    def sbgn_startup(self):
        logger.info('Initializing SBGNViz connection...')
        self.user_id = '%s' % uuid.uuid4()
        # Initialize sockets
        self.socket_s = SocketIO('localhost', self.sbgnviz_port)
        self.socket_s.emit('agentCurrentRoomRequest', self.on_subscribe)


    def on_subscribe(self, room):
        event = 'subscribeAgent'
        self.room_id = room
        user_info = {'userName': self.user_name,
                     'room': self.room_id,
                     'userId': self.user_id}
        self.socket_s.on('message', self.on_sbgnviz_message)

        self.socket_s.emit(event, user_info)

    def on_user_list(self, user_list):
        self.current_users = user_list

    def send_to_bob(self, msg):
        self.socket_b.sendall(msg)

    def on_sbgnviz_message(self, data):
        if not isinstance(data, dict):
            return
        comment = data.get('comment')
        if comment and comment.startswith('bob:'):
            text = comment[4:].strip()
            msg = '(tell :content (started-speaking :mode text :uttnum 1 ' + \
                    ':channel Desktop :direction input))'
            self.send_to_bob(msg)
            msg = '(tell :content (stopped-speaking :mode text :uttnum 1 ' + \
                    ':channel Desktop :direction input))'
            self.send_to_bob(msg)
            msg = '(tell :content (word "%s" :uttnum %d :index 1 ' % (text, self.bob_uttnum) + \
                    ':channel Desktop :direction input))'
            self.send_to_bob(msg)
            msg = '(tell :content (utterance :mode text :uttnum %d ' % self.bob_uttnum + \
                    ':text "%s" ' % text + \
                    ':channel Desktop :direction input))'
            self.send_to_bob(msg)
            self.bob_uttnum += 1

    def on_bob_message(self, data):
        # Check what kind of message it is
        kl = KQMLList.from_string(data)
        content = kl.get_keyword_arg(':content')
        logger.info('Got message with content: %s' % content)
        if not content:
            return
        if ('%s' % content.data[0]).lower() == 'spoken':
            spoken_phrase = get_spoken_phrase(content)
            self.bob_to_sbgn_say(spoken_phrase)
        elif ('%s' % content.data[0]).lower() == 'display-model':
            model = get_model(content)
            self.bob_to_sbgn_display(model)

    def bob_to_sbgn_say(self, spoken_phrase):

        msg = {'room': self.room_id,
               'comment': spoken_phrase,
               'userName': self.user_name,
               'userId': self.user_id,
               'targets': '*',
               'time': 1}
        print_json(msg)
        self.socket_s.emit('agentMessage', msg)
        self.bob_to_sbgn_display(get_example_model())

    def bob_to_sbgn_display(self, model):
        sa = SBGNAssembler()
        sa.add_statements(model)
        sbgn_content = sa.make_model()
        self.socket_s.emit('agentNewFileRequest', {'room':self.room_id})
        self.socket_s.wait(seconds=0.1)
        logger.info('sbgn_content %s'  % sbgn_content)
        sbgn_params = {'graph': sbgn_content, 'type': 'sbgn', 'room': self.room_id, 'userId': self.user_id}
        self.socket_s.emit('agentMergeGraphRequest', sbgn_params)



def print_json(js):
    s = json.dumps(js, indent=1)
    print(s)

def get_spoken_phrase(content):
    say_what = content.get_keyword_arg(':what')
    say_what = say_what.string_value()
    return say_what

def get_model(content):
    model = content.get_keyword_arg(':model')
    model = model.string_value()
    return model

if __name__ == '__main__':

    bsb = BSB()
    bsb.start()
