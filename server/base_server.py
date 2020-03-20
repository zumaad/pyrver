
from typing import Dict
import socket
from handlers.http_handlers import HttpBaseHandler, AsyncReverseProxyHandler
from handlers.handler_manager import ManageHandlers
from utils.general_utils import HttpResponse, HttpRequest, handle_exceptions
from utils.custom_exceptions import ClientClosingConnection
from abc import ABC, abstractmethod
import logging



class BaseServer(ABC):
    LOGGER = logging.getLogger("base server")
    LOGGER.setLevel(logging.DEBUG)


    def __init__(self, settings: Dict, host: str = '0.0.0.0', port: int = 9999):
        self.host = host
        self.port = port
        self.request_handlers = ManageHandlers(settings,self).prepare_handlers()
        self.LOGGER.info(f'listening on port {self.port}')
    
    def init_master_socket(self):
        """ 
        Every server will have some concept of a socket that listens for connections 
        """
        master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        master_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        master_socket.bind((self.host, self.port))
        master_socket.listen()
        self.master_socket = master_socket
        
    def handle_client_request(self, http_request: HttpRequest) -> HttpResponse:
        """
        every server should have a way to handle a client's request, there are generally two possibilities:
        1. the client sends an empty message (when they disconnect)
        2. the client sends some data that should be parsed.    
        """
        for handler in self.request_handlers:
            if handler.should_handle(http_request):
                http_response = handler.handle_request(http_request)
                return http_response
                
        http_error_response = HttpResponse(400, 'No handler could handle your request, check the matching criteria in settings.py')
        return http_error_response
        
    def start_loop(self) -> None:
        self.init_master_socket()
        self.loop_forever()
    
    def stop_loop(self) -> None:
        self.master_socket.close()
    
    def close_client_connection(self, client_socket) -> None:
        self.LOGGER.info('closing client connection')
        client_socket.close()
        
    @abstractmethod
    def loop_forever(self) -> None:
        pass

    @abstractmethod
    def handle_client(self, client) -> None:
        pass

    @abstractmethod
    def accept_new_client(self, new_client) -> None:
        pass

    @abstractmethod
    def get_type(self) -> str:
        pass