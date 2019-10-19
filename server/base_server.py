
from typing import Dict
from handlers.http_handlers import HttpBaseHandler
from handlers.handler_manager import ManageHandlers
from utils.general_utils import HttpResponse, handle_exceptions,parse_http_request


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
        raw_request = None 
        try:
            raw_request = client_socket.recv(1024)
        except (ConnectionResetError, TimeoutError) as e: 
            handle_exceptions(e)
        #clients (such as browsers) will send an empty message when they are closing
        #their side of the connection.
        if not raw_request: 
            self.on_no_received_data(client_socket)  
        else:
            self.on_received_data(client_socket, raw_request)

    def on_received_data(self, client_socket, raw_data):
        http_request = parse_http_request(raw_data)
        self.update_statistics(responses_sent=1, requests_recv=1)
        for handler in self.request_handlers:
            if handler.should_handle(http_request):
                handler.raw_http_request = raw_data
                self.on_compatible_handler(client_socket, handler)
                break
        else:
            self.on_no_compatible_handler(client_socket)

    def on_no_received_data(self, client_socket):
        print("closing client connection!")
        self.close_client_connection(client_socket)