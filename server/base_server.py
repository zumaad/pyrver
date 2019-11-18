
from typing import Dict
import socket
from handlers.http_handlers import HttpBaseHandler, AsyncReverseProxyHandler
from handlers.handler_manager import ManageHandlers
from utils.general_utils import HttpResponse, HttpRequest, handle_exceptions
from utils.custom_exceptions import ClientClosingConnection
from abc import ABC, abstractmethod
import logging



class BaseServer(ABC):
    LOGGER = logging.getLogger("server")
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
        
    def send_all(self, client_socket, response: bytes) -> None:
        """ 
        I can't just use the sendall method on the socket object because it throws an error when it can't send
        all the bytes for whatever reason (typically other socket isn't ready for reading i guess) and you can't just catch
        the error and try again because you have no clue how many bytes were actually written. However, using the send
        method gives you much finer control as it returns how many bytes were written, so if all the bytes couldn't be written
        you can truncate your message accordingly and repeat.  
        """
        BUFFER_SIZE = 1024 * 16
        while response:
            try:
                bytes_sent = client_socket.send(response[:BUFFER_SIZE])
                if bytes_sent < BUFFER_SIZE:
                    response = response[bytes_sent:]
                else:
                    response = response[BUFFER_SIZE:]
            except BlockingIOError: 
                continue

    def handle_client_request(self, client_socket) -> None:
        """
        every server should have a way to handle a client's request, there are generally two possibilities:
        1. the client sends an empty message (when they disconnect)
        2. the client sends some data that should be parsed.

        the reason on_received_data is is its on method instead of bieng stuck in here as its pretty small is
        because i can imagine that diff server implementation want to handle the received data differently. This way,
        if thats the case, they can still inherit handle_client_request and override on_received_data instead of having
        to override handle_client_request and have to reimplement a lot more
        
         """
        raw_request = None 
        raw_request = client_socket.recv(1024)
        self.LOGGER.info(raw_request)
        #clients (such as browsers) will send an empty message when they are closing
        #their side of the connection.
        if not raw_request:
            self.LOGGER.info("empty bytes sent!")
            raise ClientClosingConnection("client is closing its side of the connection, clean up connection")
        else:
            self.on_received_data(client_socket, raw_request)

    def on_received_data(self, client_socket, raw_data):
        parsed_data = self.parse_raw_data(raw_data)
        for handler in self.request_handlers:
            if handler.should_handle(parsed_data):
                self.when_compatible_handler(client_socket, handler, raw_data)
                break
        else:
            self.when_no_compatible_handler(client_socket)
    
    def parse_raw_data(self, raw_data):
        return HttpRequest.from_bytes(raw_data)
    
    def when_compatible_handler(self, client_socket, handler, raw_data):
        self.LOGGER.info("calling send all")
        handler.raw_http_request = raw_data
        if isinstance(handler, AsyncReverseProxyHandler):
            handler.handle_request(client_socket)
        else:
            http_response = handler.handle_request()
            self.send_all(client_socket, http_response)

    def when_no_compatible_handler(self, client_socket):
        http_error_response = HttpResponse(400, 'No handler could handle your request, check the matching criteria in settings.py').dump()
        self.send_all(client_socket, http_error_response)

    def start_loop(self) -> None:
        self.init_master_socket()
        self.loop_forever()
    
    def stop_loop(self) -> None:
        self.master_socket.close()
        
    @abstractmethod
    def close_client_connection(self, client_socket) -> None:
        pass
    
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