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
        Making this a class because I may want extend it later such that just using a dict would be inconvenient
        The reason the host and port are extracted whereas the other headers aren't is because those peices of info
        are needed often and they don't exist seperately in the dictionary meaning i cant just do headers['port']. 
        So whenever someone wants just the port or just the host the splitting logic has to be done. So, might as well do it 
        in here to begin with. 
        """

        self.request_type = request_type 
        self.requested_url = requested_url
        self.port = ''
        self.host = ''
        if 'Host' in headers:
            self.host,self.port = headers['Host'].split(':') #host is something like gooby.com:3333
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

class HttpResponse:
    
    def __init__(self, response_code :int=200, body: Union[str,bytes] = '', additional_headers: Dict = {}):
        """ 
        The body doesn't only accept strings because I read the files in binary and get bytes and I don't 
        want to have to decode it only to encode it again. The reason i read it in bytes is because i need to return
        bytes eventually, so it avoids repetative encoding and decoding of large text. 
        """
        self.status_line = f'HTTP/1.1 {response_code}'
        self.body = body.encode() if isinstance(body,str) else body
        self.headers = {'Content-Type':'text/html; charset=UTF-8','Content-Length':f'{len(body)}'}
        self.headers.update(additional_headers)
        
    def dump(self) -> bytes:
        status_line = self.status_line + '\r\n'
        header_list = [f'{header_name}: {value}' for header_name, value in self.headers.items()]
        header_lines = '\r\n'.join(header_list) + '\r\n\r\n' #needs to be two new lines characters after headers
        return status_line.encode() + header_lines.encode() + self.body
    
    def __repr__(self) -> str:
        return self.dump().decode()

class Range:
    def __init__(self, lower_bound: Union[float,int], upper_bound: Union[float,int]):
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
    
    def __contains__(self, num: float):
        return num >= self.lower_bound and num < self.upper_bound
    
    def __repr__(self):
        return f'Range({self.lower_bound}, {self.upper_bound})'