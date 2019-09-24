from enum import Enum
from typing import Union, Dict, List, Any
import logging
import datetime
import json

class SocketType(Enum):
    MASTER_SOCKET = 1
    CLIENT_SOCKET = 2

class ClientInformation:
    def __init__(self, addr: Union[str, int, None], socket_type: SocketType):
        self.addr = addr
        self.socket_type = socket_type

class HttpRequest:
    def __init__(self, request_type: str, requested_url: str, headers: Dict, payload: str):
        """ 
        The reason the host and port are extracted whereas the other headers aren't is because those peices of info
        are needed often and they don't exist seperately in the dictionary meaning i cant just do headers['port']. 
        So whenever someone wants just the port or just the host the splitting logic has to be done. So, might as well do it 
        in here to begin with. 
        """

        self.request_type = request_type
        self.requested_url = requested_url
        self.host,self.port = headers['Host'].split(':')  #host is something like gooby.com:3333
        self.headers = headers
        self.payload = payload

    def __getitem__(self, request_part):
        """ 
        This is implemented so that accessing parts of a request are made easier as the client doesn't need
        to know whether a certain part of a request exists in the headers field of this class or directly as an instance variable.
        """

        if request_part == 'url':
            return self.requested_url
        elif request_part == 'port':
            return self.port
        elif request_part == 'host':
            return self.host
        else:
            return self.headers[request_part]


    def __repr__(self) -> str:
        return str(vars(self))

def parse_http_request(raw_http_request: bytes) -> HttpRequest:
    http_request_lines = raw_http_request.decode().split('\r\n')
    method,requested_url = http_request_lines[0].split()[:2] #the first two words on the first line of the request
    headers = {header.split(': ')[0]:header.split(': ')[1] for header in http_request_lines[1:-2]}
    payload = http_request_lines[-1]
    return HttpRequest(method, requested_url, headers, payload)


def settings_parser() -> Dict:
    with open("settings.json",'r') as settings:
        settings_dic = json.loads(settings.read())
    return settings_dic
    

def log_debug_info(*args: Any, stdout_print:bool = False) -> None:
    str_args = [str(arg) for arg in args]
    str_args.append(str(datetime.datetime.now()))
    logs = ' '.join(str_args)
    if stdout_print:
        print(logs)
        logging.debug(logs)
    else:
        logging.debug(logs)

def handle_exceptions(exception: Exception, socket_wrapper) -> None:
    if isinstance(exception,ConnectionResetError):
        log_debug_info("connection reset error, disconnecting: ", socket_wrapper.data.addr)
    elif isinstance(exception, TimeoutError):
        log_debug_info("time out error, disconnecting: ", socket_wrapper.data.addr)