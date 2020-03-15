import socket
from typing import Dict
import selectors
from collections import namedtuple
from handlers.handler_manager import ManageHandlers
from .base_server import BaseServer
from handlers.http_handlers import HttpBaseHandler, AsyncReverseProxyHandler
from utils.general_utils import ClientInformation, HttpResponse, handle_exceptions, HttpRequest, SocketType, SocketTasks
from utils.custom_exceptions import ClientClosingConnection, NotValidHttpFormat
from event_loop.event_loop import EventLoop, ResourceTask


class PurelySync(BaseServer):
    def __init__(self, settings: Dict, host: str = '0.0.0.0', port: int = 9999):
        super().__init__(settings, host, port)
        self.event_loop = EventLoop()
    
    def get_type(self) -> str:
        #so i don't have to import this class for type hinting in a file that this file imports.....
        return 'sync'
        
    def init_master_socket(self) -> None:
        super().init_master_socket()
        self.master_socket.setblocking(False)
           
    def loop_forever(self) -> None:
        self.event_loop.run_coroutine(self.loop)
        self.event_loop.loop()
    
    def accept_new_client(self, new_client_socket):
        new_client_socket.setblocking(False)

    def loop(self) -> None:
        while True:
            yield ResourceTask(self.master_socket, 'readable')
            new_client_socket, addr = self.master_socket.accept()
            self.accept_new_client(new_client_socket)
            self.event_loop.run_coroutine(self.handle_client, new_client_socket)
        
    def handle_client(self, client_socket):
        while True:
            yield ResourceTask(client_socket, 'readable')
            try:
                http_response = self.handle_client_request(client_socket)
                # self.LOGGER.info(http_response.decode())
                yield from self.send_all(client_socket, http_response)
            except (ClientClosingConnection, socket.timeout, ConnectionResetError, TimeoutError,BrokenPipeError):
                self.close_client_connection(client_socket)
                break
    
    def read_all(self, client_socket) -> bytes:
        pass

    def send_all(self, client_socket, response: bytes) -> None:
        BUFFER_SIZE = 1024 * 16
        while response:
            bytes_sent = 0
            try:
                bytes_sent = client_socket.send(response[:BUFFER_SIZE])
                #pretty sure this can just be changed to response = response[bytes_sent:]
                if bytes_sent < BUFFER_SIZE:
                    response = response[bytes_sent:]
                else:
                    response = response[BUFFER_SIZE:]
            except BlockingIOError: 
                yield ResourceTask(client_socket, 'writable')
            except BrokenPipeError:
                self.close_client_connection(client_socket)
                break
    
    def close_client_connection(self, client_socket) -> None:
        self.LOGGER.info('closing client connection')
        

    def use_handler(self, client_socket, handler, raw_data) -> bytes:
        handler.raw_http_request = raw_data
        if isinstance(handler, AsyncReverseProxyHandler):
            self.LOGGER.info("why tf is this bieng run!!!")
            #http_response = yield from handler.handle_request(client_socket)
        else:
            http_response = handler.handle_request()
            self.LOGGER.info("hello!!!!!")
        return http_response
    