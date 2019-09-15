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
        self.request_type = request_type
        self.requested_url = requested_url
        self.headers = headers
        self.payload = payload
    
    def __repr__(self) -> str:
        return str(vars(self))



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