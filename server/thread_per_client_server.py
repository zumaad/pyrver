from .base_server import BaseServer
from typing import Dict
import socket
from utils.general_utils import execute_in_new_thread
from utils.custom_exceptions import ClientClosingConnection,NotValidHttpFormat


class ThreadPerClient(BaseServer):
    """ 
    This implementation of the server creates a new thread for each new client and
    the client is handled entirely within that thread. 
    """
   
    def loop_forever(self):
        while True:
            new_client, addr = self.master_socket.accept()
            self.accept_new_client(new_client)

    def accept_new_client(self, new_client):
        print("Accepting new client")
        #if client is idle for this long, an error should be raised and should signal closing
        #the connection
        new_client.settimeout(3) 
        execute_in_new_thread(self.handle_client, (new_client,))
        
    def handle_client(self, client):
        while True:
            try:
                self.handle_client_request(client)
            except (ClientClosingConnection, NotValidHttpFormat, socket.timeout, ConnectionResetError, TimeoutError, BrokenPipeError):
                self.close_client_connection(client)
                break
            except NotValidHttpFormat:
                self.send_all(client, b'This server only responds to http requests')
                self.close_client_connection(client)
        print("ending thread")
            
    def close_client_connection(self, client_socket) -> None:
        print("closing connection!")
        client_socket.close()