import socket
import argparse
import selectors
from utils import ClientInformation, handle_exceptions, log_debug_info, SocketType, settings_parser, parse_http_request, HttpResponse
from typing import Dict, Tuple, Union, Any, List, Callable
import logging
from handlers import ManageHandlers,HttpBaseHandler


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
    
def accept_new_client(master_socket) -> None:
    new_client_socket, addr = master_socket.accept()
    new_client_socket.setblocking(False)
    client_manager.register(new_client_socket, selectors.EVENT_READ | selectors.EVENT_WRITE, data = ClientInformation(addr,SocketType.CLIENT_SOCKET))
    list_of_sockets.append(new_client_socket)

def handle_client_request(socket_wrapper, events, handlers: List[HttpBaseHandler]) -> None:
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
            http_request = parse_http_request(recv_data)
            for handler in handlers:
                if handler.should_handle(http_request):
                    http_response = handler.handle_request()
                    send_all(client_socket,http_response)
                    return
            http_error_response = HttpResponse(400, 'No handler could handle your request, check the matching criteria in settings.json').dump()
            send_all(client_socket, http_error_response)

            
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
    print("server loop")
    while True:
        ready_sockets = client_manager.select()
        for socket_wrapper, events in ready_sockets:
            if socket_wrapper.data.socket_type == SocketType.MASTER_SOCKET:
                accept_new_client(socket_wrapper.fileobj)
            elif socket_wrapper.data.socket_type == SocketType.CLIENT_SOCKET:
                handle_client_request(socket_wrapper, events, handlers) 

def main() -> None:
    settings = settings_parser()
    relevant_task_handlers = ManageHandlers(settings).pick_handlers()
    init_master_socket()
    server_loop(relevant_task_handlers)

if __name__ == "__main__":
    main()