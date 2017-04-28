import sys
import time
import json
import uuid
import base64
import random
import select
import socket
import logging
logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('BSB')
from socketIO_client import SocketIO

from indra.statements import stmts_from_json
from indra.assemblers import SBGNAssembler

from kqml import *


class BSB(object):
    def __init__(self,  bob_port=6200, sbgnviz_port=3000):
        self.user_name = 'BOB'

        self.bob_port = bob_port
        self.sbgnviz_port = sbgnviz_port

        # Startup sequences
        self.bob_startup()
        self.sbgn_startup() 
        msg = '(tell :content (start-conversation))'
        self.socket_b.sendall(msg)

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
                            parts = data.split('\n')
                            for part in parts:
                                if part:
                                    self.on_bob_message(part)
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
        msg = '(subscribe :content (tell &key :content (display-model . *)))'
        self.socket_b.sendall(msg)
        msg = '(subscribe :content (tell &key :content (display-image . *)))'
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
        self.socket_s.emit('agentNewFileRequest', {'room': self.room_id})
        self.bob_to_sbgn_say('Hi there! Give me a minute to get started ' + 
                             'and then tell me what you want to do.')

    def on_user_list(self, user_list):
        self.current_users = user_list

    def send_to_bob(self, msg):
        self.socket_b.sendall(msg)

    def on_sbgnviz_message(self, data):
        if not isinstance(data, dict):
            return
        comment = data.get('comment')
        if isinstance(comment, dict):
            comment = comment.get('text')
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
        elif comment and comment == 'reset bob':
            msg = '(tell :content (start-conversation))'
            self.send_to_bob(msg)


    def on_bob_message(self, data):
        logger.debug('data: ' + data)
        # Check what kind of message it is
        kl = KQMLPerformative.from_string(data)
        head = kl.head()
        content = kl.get('content')
        if head == 'tell' and content.head().lower() == 'display-model':
            parts = data.split('\n')
            if len(parts) > 1:
                logger.error('!!!!!!!!!!!!\nMessage with multiple parts\n ' +
                             '!!!!!!!!!!!')
                logger.error(parts)
        logger.info('Got message with head: %s' % head)
        logger.info('Got message with content: %s' % content)
        if not content:
            return
        if content.head().lower() == 'spoken':
            spoken_phrase = get_spoken_phrase(content)
            self.bob_to_sbgn_say(spoken_phrase)
        elif content.head().lower() == 'display-model':
            stmts_json = content.gets('model')
            stmts = decode_indra_stmts(stmts_json)
            self.bob_to_sbgn_display(stmts)
        elif content.head().lower() == 'display-image':
            image_type = content.gets('type')
            path = content.gets('path')
            self.bob_show_image(path, image_type)

    def bob_to_sbgn_say(self, spoken_phrase):
        msg = {'room': self.room_id,
               'comment': {'text': spoken_phrase},
               'userName': self.user_name,
               'userId': self.user_id,
               'targets': '*',
               'time': 1}
        #print_json(msg)
        self.socket_s.emit('agentMessage', msg)

    def bob_to_sbgn_display(self, stmts):
        sa = SBGNAssembler()
        sa.add_statements(stmts)
        sbgn_content = sa.make_model()
        self.socket_s.emit('agentNewFileRequest', {'room': self.room_id})
        self.socket_s.wait(seconds=0.1)
        logger.info('sbgn_content generated')
        sbgn_params = {'graph': sbgn_content, 'type': 'sbgn',
                       'room': self.room_id, 'userId': self.user_id}
        self.socket_s.emit('agentMergeGraphRequest', sbgn_params)

    def bob_show_image(self, file_name, image_type):
        logger.info('showing image')
        with open(file_name, 'rb') as fh:
            img_content = fh.read()
        try:
            tab_id, tab_label = image_tab_map[image_type]
        except KeyError:
            logger.error('Unknown image type: %s' % image_type)
            tab_id = 99
            tab_label = 'Other'
        img = base64.b64encode(img_content)
        img = 'data:image/png;base64,%s' % img
        image_params = {'img': img, 'fileName': file_name,
                        'tabIndex': tab_id, 'tabLabel': tab_label,
                        'room': self.room_id, 'userId': self.user_id}
        self.socket_s.emit('agentSendImageRequest', image_params)

def decode_indra_stmts(stmts_json_str):
    stmts_json = json.loads(stmts_json_str)
    stmts = stmts_from_json(stmts_json)
    return stmts

def print_json(js):
    s = json.dumps(js, indent=1)
    print(s)

def get_spoken_phrase(content):
    say_what = content.gets('what')
    return say_what

image_tab_map = {
    'reactionnetwork': (1, 'RXN'),
    'contactmap': (2, 'CM'),
    'influencemap': (3, 'IM'),
    'simulation': (4, 'SIM')
    }

if __name__ == '__main__':
    bsb = BSB()
    bsb.start()
