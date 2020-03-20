from .base_server import BaseServer
from typing import Dict
import socket
from utils.general_utils import execute_in_new_thread, HttpRequest, read_all, send_all
from utils.custom_exceptions import ClientClosingConnection,NotValidHttpFormat


class ThreadPerClient(BaseServer):
    """ 
    This implementation of the server creates a new thread for each new client and
    the client is handled entirely within that thread. 
    """

    def get_type(self) -> str:
        return 'threadperclient'
   
    def loop_forever(self):
        while True:
            new_client, addr = self.master_socket.accept()
            self.accept_new_client(new_client)
            execute_in_new_thread(self.handle_client, (new_client,))

    def accept_new_client(self, new_client):
        #if client is idle for this long, an error should be raised and should signal closing
        #the connection
        new_client.settimeout(3) 
        
    def handle_client(self, client):
        while True:
            try:
                raw_client_request = read_all(client)
                http_request = HttpRequest.from_bytes(raw_client_request)
                http_response = self.handle_client_request(http_request)
                send_all(client, http_response.dump())
            except (ClientClosingConnection, NotValidHttpFormat, socket.timeout, ConnectionResetError, TimeoutError, BrokenPipeError):
                self.close_client_connection(client)
                break