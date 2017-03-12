import sys
import time
import json
import random
import select
from socketIO_client import SocketIO
import socket

from kqml import *


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
    _id_symbols = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    def generate_id(length=32, symbols=_id_symbols):
        symbol_gen = (symbols[random.randrange(0, len(symbols))]
                      for i in range(length))
        return ''.join(symbol_gen)

    user_name = 'BOB'
    user_id = generate_id()
    event = 'subscribeAgent'
    user_info = {'userName': user_name,
                 'room': room_id,
                 'userId': user_id}
    sock.on('message', dummy)
    sock.on('userList', dummy)
    sock.emit(event, user_info, dummy)

def dummy(arg1):
    print(arg1)

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
                    if not data:
                        continue
        except KeyboardInterrupt:
            break
    socket_s.emit('disconnect')
    socket_s.disconnect()
