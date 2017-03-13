import sys
import time
import json
import uuid
import random
import select
import socket
import logging
from socketIO_client import SocketIO

from kqml import *

logger = logging.getLogger('bsb')

def dummy(arg1):
    print(arg1)

class BSB(object):
    def __init__(self, room_id, bob_port=6200, sbgnviz_port=3000):
        self.user_name = 'BOB'
        self.room_id = room_id
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
        self.socket_b = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_b.connect(('localhost', self.bob_port))
        msg = '(register :name bsb)'
        self.socket_b.sendall(msg)
        msg = '(subscribe :content (tell &key :content (spoken . *)))'
        self.socket_b.sendall(msg)
        msg = '(tell :content (module-status ready))'
        self.socket_b.sendall(msg)

    def sbgn_startup(self):
        logger.info('Initializing SBGNViz connection...')
        self.user_id = '%s' % uuid.uuid4()
        # Initialize sockets
        self.socket_s = SocketIO('localhost', self.sbgnviz_port)
        event = 'subscribeAgent'
        user_info = {'userName': self.user_name,
                     'room': self.room_id,
                     'userId': self.user_id}
        self.socket_s.on('message', self.on_sbgnviz_message)
        self.socket_s.on('userList', self.on_user_list)
        self.socket_s.emit(event, user_info, self.on_user_list)

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
            msg = '(tell :content (word "%s" :uttnum 1 :index 1 ' % text + \
                    ':channel Desktop :direction input))'
            self.send_to_bob(msg)
            msg = '(tell :content (utterance :mode text :uttnum 1 ' + \
                    ':text "%s" ' % text + \
                    ':channel Desktop :direction input))'
            self.send_to_bob(msg)

    def on_bob_message(self, data):
        target_users = [{'id': user['userId']} for user in self.current_users]
        spoken_phrase = get_spoken_phrase(data)
        msg = {'room': self.room_id,
               'comment': spoken_phrase,
               'userName': self.user_name,
               'userId': self.user_id,
               'targets': target_users,
               'time': 1}
        print_json(msg)
        self.socket_s.emit('agentMessage', msg, lambda: None)

def print_json(js):
    s = json.dumps(js, indent=1)
    print(s)

def get_spoken_phrase(data):
    kl = KQMLList.from_string(data)
    content = kl.get_keyword_arg(':content')
    say_what = content.get_keyword_arg(':what')
    say_what = say_what.string_value()
    return say_what

if __name__ == '__main__':
    room_id = sys.argv[1]
    bsb = BSB(room_id)
    bsb.start()
