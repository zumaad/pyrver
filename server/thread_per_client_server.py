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
    def __init__(self, settings: Dict, host: str = '0.0.0.0', port: int = 9999):
        super().__init__(settings, host, port)

    def init_master_socket(self):
        master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        master_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        master_socket.bind((self.host, self.port))
        master_socket.listen()
        # master_socket.setblocking(False)
        self.master_socket = master_socket

    def start_loop(self):
        self.init_master_socket()
        self.loop_forever()

    def stop_loop(self):
        pass

    def loop_forever(self):
        while True:
            new_client, addr = self.master_socket.accept()
            self.accept_new_client(new_client)

    def accept_new_client(self, new_client):
        #if client is idle for this long, an error should be raised and should signal closing
        #the connection
        new_client.settimeout(10) 
        execute_in_new_thread(self.handle_client, (new_client,))
        
    def handle_client(self, client):
        while True:
            try:
                self.handle_client_request(client)
            except (ClientClosingConnection, socket.timeout):
                self.close_client_connection(client)
                break
        print("ending thread")

    def on_no_received_data(self, client_socket):
        raise ClientClosingConnection("client is closing connection. Thread should be terminated.")
            
    def close_client_connection(self, client_socket) -> None:
        print("closing connection!")
        client_socket.close()