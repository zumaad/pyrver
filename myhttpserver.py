import socket
import argparse
import selectors
from utils import ClientInformation, handle_exceptions, log_debug_info, SocketType, settings_parser, parse_http_request, HttpResponse, settings_analyzer, settings_preparer
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
parser.add_argument('--port','-p',type=int, default=9999)
parser.add_argument('--settings','-s',type=int)
args = parser.parse_args()  

class Server:
    def __init__(self, settings: Dict, host: str = '0.0.0.0', port: int = 9999):
        self.request_handlers = ManageHandlers(settings, self.update_statistics).prepare_handlers()
        self.client_manager = selectors.DefaultSelector()
        self.host = host
        self.port = port
        print(f'listening on port {self.port}')
        self.statistics = {'bytes_sent':0, 'bytes_recv':0, 'requests_recv':0, 'responses_sent':0}
        
    def accept_new_client(self, master_socket) -> None:
        new_client_socket, addr = master_socket.accept()
        new_client_socket.setblocking(False)
        self.client_manager.register(new_client_socket, selectors.EVENT_READ | selectors.EVENT_WRITE, data = ClientInformation(addr,SocketType.CLIENT_SOCKET))

    def on_compatible_handler(self, client_socket, handler: HttpBaseHandler, data_client_sent: bytes) -> None:
        """ 
        This function was made to encapsulate the whole process of getting an http response
        and sending it to a client so that i could just pass this function as a target of a new thread
        if i wanted to use a thread based handler (new thread for every request) 
        """
        handler.raw_http_request = data_client_sent
        http_response = handler.handle_request()
        self.update_statistics(bytes_recv=len(data_client_sent), bytes_sent=len(http_response))
        self.send_all(client_socket, http_response)

    def on_no_compatible_handler(self, client_socket) -> None:
        http_error_response = HttpResponse(400, 'No handler could handle your request, check the matching criteria in settings.py').dump()
        self.update_statistics(bytes_sent=len(http_error_response))
        self.send_all(client_socket, http_error_response)
    
    def execute_in_new_thread(self, func, args):
        new_thread = threading.Thread(target = func, args = args)
        new_thread.daemon = True
        new_thread.start()

    def handle_client_request(self, socket_wrapper, events) -> None:
        recv_data = None 
        client_socket = socket_wrapper.fileobj
        if events & selectors.EVENT_READ:
            try:
                recv_data = client_socket.recv(1024)
                print(recv_data)
            except (ConnectionResetError, TimeoutError) as e: 
                handle_exceptions(e, socket_wrapper)
                
            if not recv_data: #clients (such as browsers) will send an empty message when they break the connection.
                self.close_client_connection(client_socket)
            else:
                http_request = parse_http_request(recv_data)
                print(http_request)
                self.update_statistics(responses_sent=1, requests_recv=1)
                for handler in self.request_handlers:
                    if handler.should_handle(http_request):
                        if handler.threading_based:
                            self.execute_in_new_thread(self.on_compatible_handler, (client_socket, handler, recv_data,))
                        else:
                            self.on_compatible_handler(client_socket, handler, recv_data)
                        break
                #if there is no handler able to handle the request. This else clause is only executed if the for loop is finished
                #without the "break" being executed, which is only when there is no handler able to handle the request.
                else: 
                    self.on_no_compatible_handler(client_socket)

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
                    self.handle_client_request(socket_wrapper, events)

    def start_loop(self) -> None:
        self.init_master_socket()
        self.loop_forever()
    
    def stop_loop(self) -> None:
        self.master_socket.close()
        print(self.statistics)
    
def main() -> None:
    settings = settings_analyzer(settings_preparer(settings_map[args.settings]))
    print(json.dumps(settings,default=str,sort_keys=True, indent=2))
    server = Server(settings, port = args.port)
    try:
        server.start_loop()
    except KeyboardInterrupt:
        print("Stopping server :(")
        server.stop_loop()

if __name__ == "__main__":
    main()