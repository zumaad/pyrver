import socket
from typing import Dict
import selectors
from handlers.handler_manager import ManageHandlers
from .base_server import BaseServer
from handlers.http_handlers import HttpBaseHandler
from utils.general_utils import ClientInformation, HttpResponse, handle_exceptions, HttpRequest, SocketType, execute_in_new_thread

class Server(BaseServer):
    """
    This implementation of the server creates a new thread for every request, but the clients
    themselves are not given their own threads.
    """
    def __init__(self, settings: Dict, host: str = '0.0.0.0', port: int = 9999):
        super().__init__(settings, host, port)
        self.client_manager = selectors.DefaultSelector()
        # The reason for this set is that every request is handled in its own thread but before
        # the socket is able to be read, control is yeilded to the main thread which picks which sockets are to be read.
        # Since the sub thread hasn't yet exhausted that client socket, the main thread thinks that socket needs to be serviced. 
        # So this set prevents that by only servicing client sockets not currently in the set.
        self.clients_currently_being_serviced = set() 
        
    def accept_new_client(self, master_socket) -> None:
        new_client_socket, addr = master_socket.accept()
        new_client_socket.setblocking(False)
        self.client_manager.register(new_client_socket, selectors.EVENT_READ, data = ClientInformation(addr,SocketType.CLIENT_SOCKET))

    def on_compatible_handler(self, client_socket, handler: HttpBaseHandler) -> None:
        http_response = handler.handle_request()
        self.send_all(client_socket, http_response)

    def on_no_compatible_handler(self, client_socket) -> None:
        http_error_response = HttpResponse(400, 'No handler could handle your request, check the matching criteria in settings.py').dump()
        self.send_all(client_socket, http_error_response)
    
    def on_received_data(self, client_socket, raw_data):
        super().on_received_data(client_socket, raw_data)
        self.clients_currently_being_serviced.remove(client_socket)
    
    def on_no_received_data(self, client_socket):
        self.close_client_connection(client_socket)

    def close_client_connection(self, client_socket) -> None:
        self.client_manager.unregister(client_socket)
        client_socket.close()      

    def init_master_socket(self) -> None:
        master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        master_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        master_socket.bind((self.host, self.port))
        master_socket.listen()
        master_socket.setblocking(False)
        self.master_socket = master_socket
        self.client_manager.register(master_socket, selectors.EVENT_READ, data=ClientInformation(None,SocketType.MASTER_SOCKET))
    
    def loop_forever(self) -> None:
        while True:
            ready_sockets = self.client_manager.select()
            for socket_wrapper, events in ready_sockets:
                if socket_wrapper.data.socket_type == SocketType.MASTER_SOCKET:
                    self.accept_new_client(socket_wrapper.fileobj)
                elif socket_wrapper.data.socket_type == SocketType.CLIENT_SOCKET:
                    client_socket = socket_wrapper.fileobj
                    if client_socket not in self.clients_currently_being_serviced:
                        self.clients_currently_being_serviced.add(client_socket)
                        execute_in_new_thread(self.handle_client_request,(client_socket,))
                    
    def start_loop(self) -> None:
        self.init_master_socket()
        self.loop_forever()
    
    def stop_loop(self) -> None:
        self.master_socket.close()
        print(self.statistics)