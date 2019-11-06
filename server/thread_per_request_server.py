import socket
from typing import Dict
import selectors
from handlers.handler_manager import ManageHandlers
from .base_server import BaseServer
from handlers.http_handlers import HttpBaseHandler
from utils.general_utils import ClientInformation, HttpResponse, handle_exceptions, HttpRequest, SocketType, execute_in_new_thread
from utils.custom_exceptions import ClientClosingConnection, NotValidHttpFormat
from queue import Queue
import threading

class ThreadPerRequest(BaseServer):
    """
    This implementation of the server creates a new thread for every request, but the clients
    themselves are not given their own threads.
    """
    def __init__(self, settings: Dict, host: str = '0.0.0.0', port: int = 9999):
        super().__init__(settings, host, port)
        self.client_manager = selectors.KqueueSelector()
        # The reason for this set is that every request is handled in its own thread but before
        # the socket is able to be read, control is yeilded to the main thread which picks which sockets are to be read.
        # Since the sub thread hasn't yet exhausted that client socket, the main thread thinks that socket needs to be serviced. 
        # So this set prevents that by only servicing client sockets not currently in the set.
        self.clients_currently_being_serviced = set() 
        self.clients_to_be_serviced = Queue()

    
    def init_master_socket(self) -> None:
        super().init_master_socket()
        self.master_socket.setblocking(False)
        self.client_manager.register(self.master_socket, selectors.EVENT_READ, data=ClientInformation(SocketType.MASTER_SOCKET))
    
    def start_threads(self):
        for _ in range(5):
            threading.Thread(target=self.handle_client).start()

    def loop_forever(self) -> None:
        self.start_threads()
        while True:
            ready_sockets = self.client_manager.select()
            for socket_wrapper, events in ready_sockets:
                if socket_wrapper.data.socket_type == SocketType.MASTER_SOCKET:
                    master_socket = socket_wrapper.fileobj
                    new_client_socket, addr = master_socket.accept()
                    self.accept_new_client(new_client_socket)
                elif socket_wrapper.data.socket_type == SocketType.CLIENT_SOCKET:
                    client_socket = socket_wrapper.fileobj
                    # print(client_socket in self.clients_currently_being_serviced)
                    print(client_socket)
                    if client_socket not in self.clients_currently_being_serviced and not client_socket._closed:
                        self.clients_currently_being_serviced.add(client_socket)
                        self.clients_to_be_serviced.put(client_socket)
                        print("put client!!")
                        
                        # execute_in_new_thread(self.handle_client,(client_socket,))
                        # self.handle_client(client_socket)
                        # execute_in_new_thread(self.handle_client,(client_socket,))
        
    def accept_new_client(self, new_client) -> None:
        new_client.setblocking(False)
        self.client_manager.register(new_client, selectors.EVENT_READ, data = ClientInformation(socket_type=SocketType.CLIENT_SOCKET))
    
    def handle_client(self):
        while True:
            client_socket = self.clients_to_be_serviced.get()
            print("After get")
            print(client_socket)

            try:
                self.handle_client_request(client_socket)
            except (ClientClosingConnection, socket.timeout, ConnectionResetError, TimeoutError, BrokenPipeError):
                # raise Exception
                print("closing client!!!!!!")
                self.close_client_connection(client_socket)
            except BlockingIOError:
                pass
            
            print("removing client")
            self.clients_currently_being_serviced.remove(client_socket)

    def close_client_connection(self, client_socket) -> None:
        self.client_manager.unregister(client_socket)
        client_socket.close()      