from enum import Enum
from typing import Union, Dict, List, Any
import logging
import datetime
import json
import threading

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
    
    @classmethod
    def from_bytes(cls, raw_http_request: bytes) -> 'HttpRequest':
        http_request_lines = raw_http_request.decode().split('\r\n')
        method,requested_url = http_request_lines[0].split()[:2] #the first two words on the first line of the request
        headers = {header.split(': ')[0]:header.split(': ')[1] for header in http_request_lines[1:-2]}
        payload = http_request_lines[-1]
        return cls(method, requested_url, headers, payload)

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

def handle_exceptions(exception: Exception) -> None:
    if isinstance(exception,ConnectionResetError):
        log_debug_info("connection reset error")
    elif isinstance(exception, TimeoutError):
        log_debug_info("time out error, disconnecting")

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

def create_weight_ranges(server_and_weights: List):
        """
        Is called when the the user wants to load balance using the weighted strategy. The purpose of this method
        is to transform a list of tuples such as: [('localhost', 4000, 1/4), ('localhost', 4500, 1/4), ('localhost', 5000, 2/4)]
        into a list of tuples like [('localhost', 4000, Range(0,.25)), ('localhost', 4500, Range(.25,.5)), ('localhost', 5000, Range(.5,1))] where
        Range is a custom object that allows for testing whether a number is between a lower bound and upper bound. The reason
        for this transformation is so that i can easily do weight based load balancing as i can just generate a random number between
        0 and 1 and and if it lands in a range then pass the request to the server associated with that range. For example,
        let say we have three servers like this: [('localhost', 4000, Range(0,.25)), ('localhost', 4500, Range(.25,.5)), ('localhost', 5000, Range(.5,1))].
        If i generate a number between 0 and 1, 1/4 of the time it will be between 0 and .25, 1/4 of the time it will be
        between .25 and .5 and 1/2 of the time it will be between .5 and 1. So, 1/4 of the time it will go to localhost:4000,
        1/4 of the time it will go to localhost:4500, and 1/2 the time it will go to localhost:5000.
        """
        weight_ranges = []
        accumulated_range = 0
        for server_name, port, weight in server_and_weights:
            lower_bound = accumulated_range
            upper_bound = lower_bound + weight
            weight_ranges.append((server_name, port, Range(lower_bound, upper_bound)))
            accumulated_range += weight
        return weight_ranges

def settings_preparer(settings: Dict) -> Dict:
    """ 
    A user of this server will write settings in the settings.py file. I want it to be
    really easy to configure the web server, but that ease for the user may result in difficulties  
    for me. So, incase i want to transform the settings to make it easier to interpret (maybe in the future
    the task blocks will be read and put into a custom class so that accessing it is cleaner than current dict access),
    that transformation can occur here. 
    """
    for task_name, task_info in settings['tasks'].items():
        if task_name == 'load_balance':
            if task_info['context']['strategy'] == 'weighted':
                task_info['context']['send_to'] = create_weight_ranges(task_info['context']['send_to'])
    return settings

#TODO
def settings_analyzer(settings: Dict) -> Dict:
    """ 
    Analyzes the settings to see if there is anything malformed such as weights in the load balancing block with 
    the weighted strategy adding up to more than 1 
    """
    return settings

def execute_in_new_thread(func, args):
    new_thread = threading.Thread(target = func, args = args)
    new_thread.daemon = True
    new_thread.start()


class ServerFactory:
    pass