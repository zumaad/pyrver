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
from typing import Dict, Tuple, Union, Any, List, Callable

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
    
class SocketType(Enum):
    MASTER_SOCKET = 1
    CLIENT_SOCKET = 2

class ClientInformation:
    def __init__(self, addr: Union[str, int, None], socket_type: SocketType):
        self.addr = addr
        self.socket_type = socket_type

class HttpRequest():
    def __init__(self, request_type: str, requested_url: str, headers: Dict, payload: str):
        self.request_type = request_type
        self.requested_url = requested_url
        self.headers = headers
        self.payload = payload
    
    def __repr__(self) -> str:
        return str(vars(self))

class HttpBaseHandler:

    def parse_http_request(self, raw_http_request: bytes) -> None:
        http_request_lines = raw_http_request.decode().split('\r\n')
        method,requested_url = http_request_lines[0].split()[:2] #the first two words on the first line of the request
        headers = {header.split(': ')[0]:header.split(': ')[1] for header in http_request_lines[1:-2]}
        payload = http_request_lines[-1]
        self.parsed_http_request = HttpRequest(method, requested_url, headers, payload)

    def handle_request(self, raw_http_request: bytes) -> bytes:
        return self.create_http_response(b'Default http response if behaviour is not overrriden in child class :)')

    def create_http_response(self, raw_body: bytes= b'') -> bytes:
        
        length = len(raw_body) if raw_body else 0
        headers = (f'HTTP/1.1 200 OK\n'
                f'Content-Type: text/html; charset=UTF-8\n'   
                f'Content-Length: {length}\n\n').encode()
        http_response = headers + raw_body if raw_body else headers
        return http_response

class StaticAssetHandler(HttpBaseHandler):
    def __init__(self, context: Any):
        self.static_directory_path = context
        self.all_files = set(pathlib.Path(context).glob('**/*')) #get all files in the static directory

    def handle_request(self, raw_http_request: bytes) -> bytes:
        """ path_to_static_file is can be either just a filename or a path to a file in case
            the requested asset is nested  
        """
    
        self.parse_http_request(raw_http_request)
        absolute_path = self.static_directory_path + self.parsed_http_request.requested_url[1:]
        print(absolute_path)
        
        # print(self.parsed_http_request)
        if pathlib.Path(absolute_path) in self.all_files:
            static_file_contents = open(absolute_path,'rb').read()
            return self.create_http_response(static_file_contents)
        else:
            return self.create_http_response(b'file not found :(')


class ManageHandlers:
    """
    picks the handler based on settings and injects the needed context for each handler
    """

    def __init__(self, tasks_and_context: Dict):
        self.tasks_and_context = tasks_and_context
        self.task_to_handler = {'static_root':StaticAssetHandler}

    def pick_handlers(self) -> List[HttpBaseHandler]:
        task_handlers: List[HttpBaseHandler] = []
        for task, context in self.tasks_and_context.items():
            if task in self.task_to_handler:
                handlerClass = self.task_to_handler[task]
                task_handlers.append(handlerClass(context))
            else:
                raise NotImplementedError
        return task_handlers


def settings_parser() -> Dict:
    with open("settings.json",'r') as settings:
        settings_dic = json.loads(settings.read())
    return settings_dic
    

def log_debug_info(*args: Any, stdout_print:bool = False) -> None:
    str_args = [str(arg) for arg in args]
    str_args.append(str(datetime.datetime.now()))
    logs = ' '.join(str_args)
    if stdout_print:
        print(logs)
        logging.debug(logs)
    else:
        logging.debug(logs)

def accept_new_client(master_socket) -> None:
    new_client_socket, addr = master_socket.accept()
    new_client_socket.setblocking(False)
    client_manager.register(new_client_socket, selectors.EVENT_READ | selectors.EVENT_WRITE, data = ClientInformation(addr,SocketType.CLIENT_SOCKET))
    list_of_sockets.append(new_client_socket)

def handle_exceptions(exception: Exception, socket_wrapper) -> None:
    if isinstance(exception,ConnectionResetError):
        log_debug_info("connection reset error, disconnecting: ", socket_wrapper.data.addr)
    elif isinstance(exception, TimeoutError):
        log_debug_info("time out error, disconnecting: ", socket_wrapper.data.addr)

def handle_client(socket_wrapper, events, handlers: List[HttpBaseHandler]) -> None:
    recv_data = None 
    client_socket = socket_wrapper.fileobj
    if events & selectors.EVENT_READ:
        try:
            recv_data = client_socket.recv(1024)
        except (ConnectionResetError, TimeoutError) as e: 
            handle_exceptions(e, socket_wrapper)
            
        if not recv_data:
            close_client_connection(socket_wrapper)
        else:
            print("in sending messages part")
            for handler in handlers:
                response = handler.handle_request(recv_data)
                send_all(client_socket,response)

def send_all(client_socket, response: bytes):
    """ I can't just use the sendall method on the socket object because it throws an error when it can't send
        all the bytes for whatever reason (typically other socket isn't ready for reading i guess) and you can't just catch
        the error and try again because you have no clue how many bytes were actually written. However, using the send
        method gives you much finer control as it returns how many bytes were written, so if all the bytes couldn't be written
        you can truncate your message accordingly and repeat.  """
    BUFFER_SIZE = 1024 #is this optimal, i have no clue :), should research what a good buffer size is.
    while response:
        bytes_sent = client_socket.send(response[:BUFFER_SIZE])
        if bytes_sent < BUFFER_SIZE:
            response = response[bytes_sent:]
        else:
            response = response[BUFFER_SIZE:]

def close_client_connection(socket_wrapper) -> None:
    log_debug_info('closing connection', socket_wrapper.data.addr,stdout_print=True)
    client_socket = socket_wrapper.fileobj
    client_manager.unregister(client_socket)
    client_socket.close()
    list_of_sockets.remove(client_socket)         

def init_master_socket() -> None:
    master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    master_socket.bind((HOST, PORT))
    master_socket.listen()
    master_socket.setblocking(False)
    client_manager.register(master_socket, selectors.EVENT_READ, data=ClientInformation(None,SocketType.MASTER_SOCKET))

def server_loop(handlers: List[HttpBaseHandler]) -> None:
    while True:
        ready_sockets = client_manager.select()
        for socket_wrapper, events in ready_sockets:
            if socket_wrapper.data.socket_type == SocketType.MASTER_SOCKET:
                accept_new_client(socket_wrapper.fileobj)
            elif socket_wrapper.data.socket_type == SocketType.CLIENT_SOCKET:
                handle_client(socket_wrapper, events, handlers)

def main() -> None:
    settings = settings_parser()
    task_handlers = ManageHandlers(settings['tasks']).pick_handlers()
    init_master_socket()
    server_loop(task_handlers)

if __name__ == "__main__":
    main()