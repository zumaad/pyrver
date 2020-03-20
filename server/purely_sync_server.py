import socket
from typing import Dict, Union, Generator
import selectors
from collections import namedtuple
from handlers.handler_manager import ManageHandlers
from .base_server import BaseServer
from handlers.http_handlers import HttpBaseHandler, AsyncReverseProxyHandler, AsyncLoadBalancingHandler
from utils.general_utils import ClientInformation, HttpResponse, handle_exceptions, HttpRequest, SocketType, SocketTasks, async_send_all, read_all
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

    def loop(self) -> Generator:
        while True:
            yield ResourceTask(self.master_socket, 'readable')
            new_client_socket, addr = self.master_socket.accept()
            self.accept_new_client(new_client_socket)
            self.event_loop.run_coroutine(self.handle_client, new_client_socket)
        
    def handle_client(self, client_socket) -> Generator:
        while True:
            yield ResourceTask(client_socket, 'readable')
            try:
                raw_client_request = read_all(client_socket)
                print(raw_client_request)
                http_request = HttpRequest.from_bytes(raw_client_request)
                http_response = yield from self.handle_client_request(http_request)
                yield from async_send_all(client_socket, http_response.dump())
            except (ClientClosingConnection, socket.timeout, ConnectionResetError, TimeoutError,BrokenPipeError):
                self.close_client_connection(client_socket)
                break

    def handle_client_request(self, http_request: HttpRequest) -> Generator:
        for handler in self.request_handlers:
            if handler.should_handle(http_request):
                if isinstance(handler, AsyncReverseProxyHandler) or isinstance(handler, AsyncLoadBalancingHandler):
                    http_response = yield from handler.handle_request(http_request)
                else:
                    http_response = handler.handle_request(http_request)

                return http_response
                
        http_error_response = HttpResponse(400, 'No handler could handle your request, check the matching criteria in settings.py')
        return http_error_response
