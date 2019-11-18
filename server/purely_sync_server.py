import socket
from typing import Dict
import selectors
from collections import namedtuple
from handlers.handler_manager import ManageHandlers
from .base_server import BaseServer
from handlers.http_handlers import HttpBaseHandler
from utils.general_utils import ClientInformation, HttpResponse, handle_exceptions, HttpRequest, SocketType, SocketTasks
from utils.custom_exceptions import ClientClosingConnection, NotValidHttpFormat


class PurelySync(BaseServer):
    def __init__(self, settings: Dict, host: str = '0.0.0.0', port: int = 9999):
        self.socket_to_tasks: Dict[socket.socket,SocketTasks] = {}
        self.client_manager = selectors.KqueueSelector()
        super().__init__(settings, host, port)
    
    def get_type(self) -> str:
        return 'sync'
        
    def init_master_socket(self) -> None:
        super().init_master_socket()
        socket_tasks = SocketTasks()
        socket_tasks.set_reading_task(self.master_socket_callback)
        self.socket_to_tasks[self.master_socket] = socket_tasks
        self.master_socket.setblocking(False)
        self.client_manager.register(self.master_socket, selectors.EVENT_READ)
    
    def loop_forever(self) -> None:
        while True:
            ready_sockets = self.client_manager.select()
            for socket_wrapper, events in ready_sockets:
                actual_socket = socket_wrapper.fileobj
                try:
                    task = self.socket_to_tasks[actual_socket]
                except KeyError:
                    self.LOGGER.warning("key error bad file descriptor!!")
                    continue
                callback, args = None,None
                if events & selectors.EVENT_READ:
                    self.LOGGER.info("executing reading task")
                    callback = task.reading_task.callback
                    args = task.reading_task.args
                elif events & selectors.EVENT_WRITE and task.writing_task is not None:
                    self.LOGGER.info("executing writing task")
                    callback = task.writing_task.callback
                    args = task.writing_task.args
                    #this is so that you don't keep trying to execute the same
                    #writing task over and over.
                    task.writing_task = None
                    
                if callback and args:
                    callback(*args)
                elif callback:
                    callback()
                
    def master_socket_callback(self):
        self.LOGGER.info("accepting new client")
        new_client_socket, addr = self.master_socket.accept()
        self.accept_new_client(new_client_socket)
    
    def accept_new_client(self, new_client) -> None:
        new_client.setblocking(False)
        socket_tasks = SocketTasks()
        socket_tasks.set_reading_task(self.handle_client, (new_client,))
        self.socket_to_tasks[new_client] = socket_tasks
        self.client_manager.register(new_client, selectors.EVENT_READ | selectors.EVENT_WRITE)
    
    def send_all(self, client_socket, response: bytes) -> None:
        BUFFER_SIZE = 1024 * 16
        while response:
            bytes_sent = 0
            try:
                bytes_sent = client_socket.send(response[:BUFFER_SIZE])
                if bytes_sent < BUFFER_SIZE:
                    response = response[bytes_sent:]
                else:
                    response = response[BUFFER_SIZE:]
            except BlockingIOError: 
                bytes_left = response[bytes_sent:]
                self.socket_to_tasks[client_socket].set_writing_task(self.send_all, (client_socket, bytes_left))
                break
            except BrokenPipeError:
                self.close_client_connection(client_socket)
                break

    
    def handle_client(self, client_socket):
        self.LOGGER.info("attempting to handle client")
        try:
            self.handle_client_request(client_socket)
        except (ClientClosingConnection, socket.timeout, ConnectionResetError, TimeoutError,BrokenPipeError):
            self.close_client_connection(client_socket)
    
    def close_client_connection(self, client_socket) -> None:
        self.LOGGER.info('closing client connection')
        del self.socket_to_tasks[client_socket]
        self.client_manager.unregister(client_socket)
        client_socket.close() 
    