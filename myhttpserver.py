import socket
import time
import argparse
from time import sleep
import selectors
import datetime
import logging
from enum import Enum
from http.server import BaseHTTPRequestHandler
from io import BytesIO
import json
import os
import pathlib

"""
design decisions i want the handlers to be in a class so that they are grouped together.
I want a mapping of tasks to handlers so that i can just look up the task in the dictionary and return the
appropriate handler instead of having a bunch of if statements. 
"""

logging.basicConfig(filename='server.log',
                            filemode='a',
                            datefmt='%H:%M:%S',
                            level=logging.DEBUG)
parser = argparse.ArgumentParser()
parser.add_argument('port')
args = parser.parse_args()

HOST = '0.0.0.0'  
PORT = int(args.port)

client_manager = selectors.DefaultSelector()
list_of_sockets = []



class ClientInformation:
    def __init__(self,addr,socket_type):
        self.addr = addr
        self.socket_type = socket_type

class HTTPRequest(BaseHTTPRequestHandler): 
    """ This class subclasses BaseHTTPRequestHandler so that
        i can take advantage of parse_request as i don't want to
        write an http parser """

    def __init__(self, request_text): 
        self.rfile = BytesIO(request_text) #parse_request from parent class assumes this is set.
        self.raw_requestline = self.rfile.readline() 
        self.error_code = self.error_message = None 
        self.parse_request() 

    def send_error(self, code, message): 
        self.error_code = code 
        self.error_message = message 

class SocketType(Enum):
    MASTER_SOCKET = 1
    CLIENT_SOCKET = 2


class StaticAssetHandler:
    def __init__(self, context):
        self.static_directory_path = context
        self.all_files = set(pathlib.Path(context).glob('**/*')) #get all files in the static directory

    def static_asset_handler(self, path_to_static_file):
        """ path_to_static_file is can be either just a filename or a path to a file in case
            the requested asset is nested  
        """
        absolute_path = self.static_directory_path + path_to_static_file
        
        if pathlib.Path(absolute_path) in self.all_files:
            static_file_contents = open(absolute_path,'rb').read()
            return static_file_contents
        else:
            return b'file does not exist'


        


class ManageHandlers:
    """
    picks the handler based on settings and injects the needed context for each handler
    """

    def __init__(self, tasks_and_context):
        self.tasks_and_context = tasks_and_context
        self.task_to_handler = {'static':StaticAssetHandler}


    def pick_handlers(self):
        task_handlers = []
        for task, context  in self.tasks_and_context.items():
            if task in self.task_to_handler:
                handlerClass = self.task_to_handler[task]
                task_handlers.append(handlerClass(context))
            else:
                raise NotImplementedError
        return task_handlers


def settings_parser():
    with open("settings.json",'r') as settings:
        settings_dic = json.loads(settings.read())
    return settings_dic
    

def log_debug_info(*args, stdout_print = False):
    str_args = [str(arg) for arg in args]
    str_args.append(str(datetime.datetime.now()))
    logs = ' '.join(str_args)
    if stdout_print:
        print(logs)
        logging.debug(logs)
    else:
        logging.debug(logs)


    

def create_http_response(body=None):
    if not body:
        length = 0
    else:
        length = len(body)
    
    headers = (f'HTTP/1.1 200 OK\n'
               f'Content-Type: text/html; charset=UTF-8\n'   
               f'Content-Length: {length}\n\n').encode()
    if body:
        return headers + body
    else:
         return headers


# with open('home.html','rb') as home_page:
#     home_page_html = home_page.read()

def accept_new_client(master_socket):
    new_client_socket, addr = master_socket.accept()
    new_client_socket.setblocking(False)
    client_manager.register(new_client_socket, selectors.EVENT_READ | selectors.EVENT_WRITE, data = ClientInformation(addr,SocketType.CLIENT_SOCKET))
    list_of_sockets.append(new_client_socket)


def handle_client(socket_wrapper, events):
    recv_data = None 
    client_socket = socket_wrapper.fileobj
    if events & selectors.EVENT_READ:
        try:
            recv_data = client_socket.recv(1024)
        except ConnectionResetError: # this is the connection reset by peer error.
            recv_data = None
            log_debug_info("connection reset error, disconnecting: ", socket_wrapper.data.addr)
        except TimeoutError:
            recv_data = None
            log_debug_info("time out error, disconnecting: ", socket_wrapper.data.addr)
	
        if not recv_data:
            close_client_connection(socket_wrapper)
        else:
            client_socket.sendall(create_http_response())
            print(recv_data)
        
def close_client_connection(socket_wrapper):
    log_debug_info('closing connection', socket_wrapper.data.addr,stdout_print=True)
    client_socket = socket_wrapper.fileobj
    client_manager.unregister(client_socket)
    client_socket.close()
    list_of_sockets.remove(client_socket)         

def init_master_socket():
    master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    master_socket.bind((HOST, PORT))
    master_socket.listen()
    master_socket.setblocking(False)
    client_manager.register(master_socket, selectors.EVENT_READ, data=ClientInformation(None,SocketType.MASTER_SOCKET))

def server_loop():
    while True:
        ready_sockets = client_manager.select()
        for socket_wrapper, events in ready_sockets:
            if socket_wrapper.data.socket_type == SocketType.MASTER_SOCKET:
                accept_new_client(socket_wrapper.fileobj)
            elif socket_wrapper.data.socket_type == SocketType.CLIENT_SOCKET:
                handle_client(socket_wrapper, events)

def main():
    settings = settings_parser()
    task_handlers = ManageHandlers(settings['tasks'])
    init_master_socket()
    server_loop()

# master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# master_socket.bind((HOST, PORT))
# master_socket.listen()
# print("listening")
# client_socket, addr = master_socket.accept()
# print('accepted client')
# sleep(5)
# while True:
#     http_message = client_socket.recv(1024)
#     print(http_message)
#     if b'GET' in http_message:
#         print(http_message.decode())
#         http_response = create_http_response(home_page_html) 
        
#         client_socket.sendall(http_response)
#     elif b'POST' in http_message:
#         print(http_message.decode())
#         print(client_socket.recv(100))
#         print("past last recv")

#         http_response = create_http_response(None) 
#         client_socket.sendall(http_response)
#     elif not http_message:
#         print(http_message)
#         print("client closing connection")
#         break

if __name__ == "__main__":
    main()