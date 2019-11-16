import socket
from typing import Dict
import selectors
from collections import namedtuple
from handlers.handler_manager import ManageHandlers
from .base_server import BaseServer
from handlers.http_handlers import HttpBaseHandler
from utils.general_utils import ClientInformation, HttpResponse, handle_exceptions, HttpRequest, SocketType, execute_in_new_thread
from utils.custom_exceptions import ClientClosingConnection, NotValidHttpFormat

task = namedtuple('task', 'callback args')
class SocketTasks:
    def __init__(self):
        self.reading_task = None
        self.writing_task = None
    
    def set_reading_task(self, callback, args=()):
        self.reading_task = task(callback, args)

    def set_writing_task(self,callback, args=()):
        self.writing_task = task(callback, args)

class PurelySync(BaseServer):
    def __init__(self, settings: Dict, host: str = '0.0.0.0', port: int = 9999):
        super().__init__(settings, host, port)
        self.client_manager = selectors.KqueueSelector()
    
    def init_master_socket(self) -> None:
        super().init_master_socket()
        socket_tasks = SocketTasks()
        socket_tasks.set_reading_task(self.master_socket_callback)
        self.master_socket.setblocking(False)
        self.client_manager.register(self.master_socket, selectors.EVENT_READ, data=socket_tasks)
    
    def loop_forever(self) -> None:
        while True:
            ready_sockets = self.client_manager.select()
            for socket_wrapper, events in ready_sockets:
                if events & selectors.EVENT_READ:
                    callback = socket_wrapper.data.reading_task.callback
                    args = socket_wrapper.data.reading_task.args
                elif events & selectors.EVENT_WRITE and socket_wrapper.data.writing_task.args is not None:
                    callback = socket_wrapper.data.reading_task.callback
                    args = socket_wrapper.data.reading_task.args

                if args:
                    callback(*args)
                else:
                    callback()

            # for socket_wrapper, events in ready_sockets:
            #     if socket_wrapper.data.socket_type == SocketType.MASTER_SOCKET:
            #         master_socket = socket_wrapper.fileobj
            #         new_client_socket, addr = master_socket.accept()
            #         self.accept_new_client(new_client_socket)
            #     elif socket_wrapper.data.socket_type == SocketType.CLIENT_SOCKET:
            #         client_socket = socket_wrapper.fileobj
            #         if events & selectors.EVENT_READ:
            #             self.handle_client(socket_wrapper)
            #         elif events & selectors.EVENT_WRITE and socket_wrapper.data.writing_task_args is not None:
            #             self.send_all(client_socket,socket_wrapper.data.context)

    def master_socket_callback(self):
        new_client_socket, addr = self.master_socket.accept()
        self.accept_new_client(new_client_socket)
    
    def accept_new_client(self, new_client) -> None:
        new_client.setblocking(False)
        socket_tasks = SocketTasks()
        socket_tasks.set_reading_task(self.handle_client, (new_client,))
        self.client_manager.register(
            new_client, selectors.EVENT_READ | selectors.EVENT_WRITE, 
            data = socket_tasks)
    
    def send_all(self, client_socket, response: bytes) -> None:
        BUFFER_SIZE = 1024 * 16
        while response:
            try:
                bytes_sent = client_socket.send(response[:BUFFER_SIZE])
                if bytes_sent < BUFFER_SIZE:
                    response = response[bytes_sent:]
                else:
                    response = response[BUFFER_SIZE:]
            except BlockingIOError: 
                #tell me when the socket is ready to write to
                self.client_manager.register(client_socket, selectors.EVENT_WRITE, data = ClientInformation(
                    socket_type=SocketType.CLIENT_SOCKET,
                    context = response[bytes_sent:]))
                break
    
    def handle_client(self, client_socket):
        try:
            self.handle_client_request(client_socket)
        except (ClientClosingConnection, socket.timeout, ConnectionResetError, TimeoutError, BrokenPipeError):
            self.close_client_connection(client_socket)
    
    def close_client_connection(self, client_socket) -> None:
        self.client_manager.unregister(client_socket)
        client_socket.close() 