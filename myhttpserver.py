import socket
import argparse
import selectors
from utils import ClientInformation, handle_exceptions, log_debug_info, SocketType, settings_parser, parse_http_request, HttpResponse, settings_analyzer, settings_preparer,execute_in_new_thread,HttpRequest
from typing import Dict, Tuple, Union, Any, List, Callable
import logging
from handlers import ManageHandlers,HttpBaseHandler
from settings import settings_map
import threading
import json

logging.basicConfig(filename='server.log',
                            filemode='a',
                            datefmt='%H:%M:%S',
                            level=logging.DEBUG)
parser = argparse.ArgumentParser()
parser.add_argument('--settings','-s',type=int)
args = parser.parse_args() 

class BaseServer:

    def __init__(self, settings: Dict, host: str = '0.0.0.0', port: int = 9999):
        self.host = host
        self.port = port
        self.request_handlers = ManageHandlers(settings, self.update_statistics).prepare_handlers()
        self.statistics = {'bytes_sent':0, 'bytes_recv':0, 'requests_recv':0, 'responses_sent':0}

    def update_statistics(self, **statistics) -> None:
        for statistic_name, statistic_value in statistics.items():
            if statistic_name in self.statistics:
                self.statistics[statistic_name] += statistic_value
            else:
                self.statistics[statistic_name] = statistic_value

    def send_all(self, client_socket, response: bytes) -> None:
        """ I can't just use the sendall method on the socket object because it throws an error when it can't send
            all the bytes for whatever reason (typically other socket isn't ready for reading i guess) and you can't just catch
            the error and try again because you have no clue how many bytes were actually written. However, using the send
            method gives you much finer control as it returns how many bytes were written, so if all the bytes couldn't be written
            you can truncate your message accordingly and repeat.  """
        BUFFER_SIZE = 1024 * 16
        while response:
            try:
                bytes_sent = client_socket.send(response[:BUFFER_SIZE])
                if bytes_sent < BUFFER_SIZE:
                    response = response[bytes_sent:]
                else:
                    response = response[BUFFER_SIZE:]
            #for when client unexpectedly drops connection, chrome does this when serving large files as it will make
            #two requests and drop the first one's connection thus resulting in this error. idk why it does that, maybe
            #i am misinterpreting something.
            except BrokenPipeError: 
                self.close_client_connection(client_socket)
                break
            except BlockingIOError: 
                print("closing connection on blocking io error")
                #DON'T THINK I SHOULD DO THIS, should just continue as client's buffer could be full, so just put pass
                self.close_client_connection(client_socket)
                break

    def on_compatible_handler(self, client_socket, handler: HttpBaseHandler) -> None:
        """
        Handles dealing with client when there is a handler that can handle the http request, meaning that
        the http request matches atleast one of the match criteria for the tasks defined in settings.py
        """
        http_response = handler.handle_request()
        self.send_all(client_socket, http_response)

    def on_no_compatible_handler(self, client_socket) -> None:
        """
        Handles dealing with the client when there is no handler that can handle the http request, meaning
        that the http request did not match any of the match criteria for any of the tasks in settings.py
        """
        http_error_response = HttpResponse(400, 'No handler could handle your request, check the matching criteria in settings.py').dump()
        self.send_all(client_socket, http_error_response)
    
    def handle_client_request(self, client_socket) -> None:
        print("handling client request")
        raw_request = None 
        try:
            print("attempting to read")
            raw_request = client_socket.recv(1024)
            print(raw_request)
        except (ConnectionResetError, TimeoutError) as e: 
            handle_exceptions(e)
        #clients (such as browsers) will send an empty message when they are closing
        #their side of the connection.
        if not raw_request: 
            print("closing client connection!")
            self.close_client_connection(client_socket)
            raise Exception("connection closed")
        else:
            http_request = parse_http_request(raw_request)
            self.update_statistics(responses_sent=1, requests_recv=1)
            for handler in self.request_handlers:
                if handler.should_handle(http_request):
                    handler.raw_http_request = raw_request
                    self.on_compatible_handler(client_socket, handler)
                    break
            else:
                self.on_no_compatible_handler(client_socket)
    
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
            print("accpeted new client")
            self.accept_new_client(new_client)

    def accept_new_client(self, new_client):
        #if client is idle for this long, an error should be raised and should signal closing
        #the connection
        new_client.settimeout(20) 
        execute_in_new_thread(self.handle_client, (new_client,))
        
    def handle_client(self, client):
        print("handling client!")
        while True:
            try:
                self.handle_client_request(client) #need to break on timeout and stuff
            except:
                break
            
    def close_client_connection(self, client_socket) -> None:
        client_socket.close()
        
class Server:
    """
    This implementation of the server creates a new thread for every request, but the clients
    themselves are not given their own threads.
    """
    def __init__(self, settings: Dict, host: str = '0.0.0.0', port: int = 9999):
        self.host = host
        self.port = port
        self.request_handlers = ManageHandlers(settings, self.update_statistics).prepare_handlers()
        self.client_manager = selectors.DefaultSelector()
        self.statistics = {'bytes_sent':0, 'bytes_recv':0, 'requests_recv':0, 'responses_sent':0}
        # The reason for this set is that every request is handled in its own thread but before
        # the socket is able to be read, control is yeilded to the main thread which picks which sockets are to be read.
        # Since the sub thread hasn't yet exhausted that client socket, the main thread thinks that socket needs to be serviced. 
        # So this set prevents that by only servicing client sockets not currently in the set.
        self.clients_currently_being_serviced = set() 
        print(f'listening on port {self.port}')

        
    def accept_new_client(self, master_socket) -> None:
        new_client_socket, addr = master_socket.accept()
        new_client_socket.setblocking(False)
        self.client_manager.register(new_client_socket, selectors.EVENT_READ, data = ClientInformation(addr,SocketType.CLIENT_SOCKET))

    def on_compatible_handler(self, client_socket, handler: HttpBaseHandler) -> None:
        http_response = handler.handle_request()
        self.send_all(client_socket, http_response)

    def on_no_compatible_handler(self, client_socket) -> None:
        http_error_response = HttpResponse(400, 'No handler could handle your request, check the matching criteria in settings.py').dump()
        self.update_statistics(bytes_sent=len(http_error_response))
        self.send_all(client_socket, http_error_response)
    
    def handle_client_request(self, client_socket) -> None:
        raw_request = None 
        try:
            raw_request = client_socket.recv(1024)
        except (ConnectionResetError, TimeoutError) as e: 
            handle_exceptions(e)
        #clients (such as browsers) will send an empty message when they are closing
        #their side of the connection.
        if not raw_request: 
            print("closing client connection!")
            self.close_client_connection(client_socket)
        else:
            http_request = HttpRequest.from_bytes(raw_request)
            self.update_statistics(responses_sent=1, requests_recv=1)
            for handler in self.request_handlers:
                if handler.should_handle(http_request):
                    handler.raw_http_request = raw_request
                    self.on_compatible_handler(client_socket, handler)
                    break
            else:
                self.on_no_compatible_handler(client_socket)
            self.clients_currently_being_serviced.remove(client_socket)
        
    def update_statistics(self, **statistics) -> None:
        for statistic_name, statistic_value in statistics.items():
            if statistic_name in self.statistics:
                self.statistics[statistic_name] += statistic_value
            else:
                self.statistics[statistic_name] = statistic_value

    def send_all(self, client_socket, response: bytes) -> None:
        """ I can't just use the sendall method on the socket object because it throws an error when it can't send
            all the bytes for whatever reason (typically other socket isn't ready for reading i guess) and you can't just catch
            the error and try again because you have no clue how many bytes were actually written. However, using the send
            method gives you much finer control as it returns how many bytes were written, so if all the bytes couldn't be written
            you can truncate your message accordingly and repeat.  """
        BUFFER_SIZE = 1024 * 16
        while response:
            try:
                bytes_sent = client_socket.send(response[:BUFFER_SIZE])
                if bytes_sent < BUFFER_SIZE:
                    response = response[bytes_sent:]
                else:
                    response = response[BUFFER_SIZE:]
            #for when client unexpectedly drops connection, chrome does this when serving large files as it will make
            #two requests and drop the first one's connection thus resulting in this error. idk why it does that, maybe
            #i am misinterpreting something.
            except BrokenPipeError: 
                self.close_client_connection(client_socket)
                break
            except BlockingIOError: 
                print("closing connection on blocking io error")
                #DON'T THINK I SHOULD DO THIS, should just continue as client's buffer could be full, so just put pass
                self.close_client_connection(client_socket)
                break
        
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

def main() -> None:
    settings = settings_analyzer(settings_preparer(settings_map[args.settings]))
    print(json.dumps(settings,default=str,sort_keys=True, indent=2))
    # server = Server(settings, port = args.port)
    server = PurelyThreadedServer(settings)
    try:
        server.start_loop()
    except KeyboardInterrupt:
        print("Stopping server :(")
        server.stop_loop()

if __name__ == "__main__":
    main()