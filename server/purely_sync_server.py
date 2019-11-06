import socket
from typing import Dict
import selectors
from handlers.handler_manager import ManageHandlers
from .base_server import BaseServer
from handlers.http_handlers import HttpBaseHandler
from utils.general_utils import ClientInformation, HttpResponse, handle_exceptions, HttpRequest, SocketType, execute_in_new_thread
from utils.custom_exceptions import ClientClosingConnection, NotValidHttpFormat


class PurelySync(BaseServer):
    def __init__(self, settings: Dict, host: str = '0.0.0.0', port: int = 9999):
        super().__init__(settings, host, port)
        self.client_manager = selectors.KqueueSelector()
        # self.clients_currently_being_serviced = set() 
    
    def init_master_socket(self) -> None:
        super().init_master_socket()
        self.master_socket.setblocking(False)
        self.client_manager.register(self.master_socket, selectors.EVENT_READ, data=ClientInformation(SocketType.MASTER_SOCKET))
    
    def loop_forever(self) -> None:
        while True:
            ready_sockets = self.client_manager.select()
            for socket_wrapper, events in ready_sockets:
                if socket_wrapper.data.socket_type == SocketType.MASTER_SOCKET:
                    master_socket = socket_wrapper.fileobj
                    new_client_socket, addr = master_socket.accept()
                    self.accept_new_client(new_client_socket)
                elif socket_wrapper.data.socket_type == SocketType.CLIENT_SOCKET:
                    client_socket = socket_wrapper.fileobj
                    # if client_socket not in self.clients_currently_being_serviced:
                    if events & selectors.EVENT_READ:
                        self.handle_client(client_socket)
                    elif events & selectors.EVENT_WRITE:
                        self.send_all(client_socket,socket_wrapper.data.context)


    def accept_new_client(self, new_client) -> None:
        new_client.setblocking(False)
        self.client_manager.register(new_client, selectors.EVENT_READ, data = ClientInformation(socket_type=SocketType.CLIENT_SOCKET))
    
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
                #tell me when the socket is ready to write to
                self.client_manager.unregister(client_socket)
                self.client_manager.register(client_socket, selectors.EVENT_WRITE, data = ClientInformation(
                    socket_type=SocketType.CLIENT_SOCKET,
                    context = response[bytes_sent:]))
                print("blocking io error")
                break
    
    def handle_client(self, client_socket):
        try:
            self.handle_client_request(client_socket)
        except (ClientClosingConnection, socket.timeout, ConnectionResetError, TimeoutError, BrokenPipeError):
            self.close_client_connection(client_socket)
        # self.clients_currently_being_serviced.remove(client_socket)

    def close_client_connection(self, client_socket) -> None:
        self.client_manager.unregister(client_socket)
        client_socket.close() 