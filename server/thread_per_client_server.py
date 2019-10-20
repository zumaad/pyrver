from .base_server import BaseServer
from typing import Dict
import socket
from utils.general_utils import execute_in_new_thread
from utils.custom_exceptions import ClientClosingConnection


class PurelyThreadedServer(BaseServer):
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
        new_client.settimeout(10) 
        execute_in_new_thread(self.handle_client, (new_client,))
        
    def handle_client(self, client):
        """

        """
        while True:
            try:
                self.handle_client_request(client)
            except (ClientClosingConnection, socket.timeout, ConnectionResetError, TimeoutError, BrokenPipeError):
                self.close_client_connection(client)
                break
        print("ending thread")

    def on_no_received_data(self, client_socket):
        """
        This is executed when the client sends an empty byte string (b''). This means the client is closing its side of the connection. This
        method raises an exception so that it can be caught in the method that calls this method and the while true loop can be broken out of to
        end the thread.
        """
        self.close_client_connection(client_socket)
        raise ClientClosingConnection("client is closing connection. Thread should be terminated.")
            
    def close_client_connection(self, client_socket) -> None:
        print("closing connection!")
        client_socket.close()