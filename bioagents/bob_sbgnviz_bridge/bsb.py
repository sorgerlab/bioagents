import sys
import time
import json
import random
import select
from socketIO_client import SocketIO
import socket

from kqml import *

user_name = 'BOB'
_id_symbols = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
def generate_id(length=32, symbols=_id_symbols):
    symbol_gen = (symbols[random.randrange(0, len(symbols))]
                  for i in range(length))
    return ''.join(symbol_gen)

user_id = generate_id()

def on_message(data):
    print(data)

def on_user_list(data):
    print(data)

def bob_startup(sock):
    msg = '(register :name bsb)'
    sock.sendall(msg)
    msg = '(subscribe :content (tell &key :content (spoken . *)))'
    sock.sendall(msg)
    msg = '(tell :content (module-status ready))'
    sock.sendall(msg)

def sbgn_startup(sock, room_id):
    event = 'subscribeAgent'
    user_info = {'userName': user_name,
                 'room': room_id,
                 'userId': user_id}
    sock.on('message', on_sbgnviz_message)
    sock.on('userList', dummy)
    sock.emit(event, user_info, dummy)

def send_to_bob(msg):
    socket_b.sendall(msg)

def dummy(arg1):
    print(arg1)

def on_sbgnviz_message(data):
    if not isinstance(data, dict):
        return
    comment = data.get('comment')
    if comment and comment.startswith('bob:'):
        text = comment[4:].strip()
        msg = '(tell :content (started-speaking :mode text :uttnum 1 ' + \
                ':channel Desktop :direction input))'
        send_to_bob(msg)
        msg = '(tell :content (stopped-speaking :mode text :uttnum 1 ' + \
                ':channel Desktop :direction input))'
        send_to_bob(msg)
        msg = '(tell :content (word "%s" :uttnum 1 :index 1 ' % text + \
                ':channel Desktop :direction input))'
        send_to_bob(msg)
        msg = '(tell :content (utterance :mode text :uttnum 1 ' + \
                ':text "%s" ' % text + \
                ':channel Desktop :direction input))'
        send_to_bob(msg)

def on_bob_message(data):
    msg = {'room': room_id, 'comment': data, 'userName': user_name,
            'userId': user_id, 'time': 1}
    socket_s.emit('agentMesage', msg, lambda: None)

if __name__ == '__main__':
    room_id = sys.argv[1]

    # Initialize sockets
    socket_s = SocketIO('localhost', '3000')
    socket_b = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_b.connect(('localhost', 6200))

    # Startup sequences
    bob_startup(socket_b)
    sbgn_startup(socket_s, room_id)

    # Wait for things to happen
    socks = [socket_b, socket_s._transport._connection.sock]
    while True:
        try:
            ready_socks, _, _ = select.select(socks, [], [])
            for sock in ready_socks:
                if sock == socket_s._transport._connection.sock:
                    socket_s.wait(seconds=0.1)
                else:
                    data, addr = sock.recvfrom(4086)
                    if data:
                        on_bob_message(data)
        except KeyboardInterrupt:
            break
    socket_s.emit('disconnect')
    socket_s.disconnect()
