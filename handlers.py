
from utils import HttpRequest
import pathlib
from typing import Any, List, Dict, Union

class HttpBaseHandler:

    def parse_http_request(self, raw_http_request: bytes) -> None:
        http_request_lines = raw_http_request.decode().split('\r\n')
        method,requested_url = http_request_lines[0].split()[:2] #the first two words on the first line of the request
        headers = {header.split(': ')[0]:header.split(': ')[1] for header in http_request_lines[1:-2]}
        payload = http_request_lines[-1]
        self.parsed_http_request = HttpRequest(method, requested_url, headers, payload)

    def handle_request(self, raw_http_request: bytes) -> bytes:
        return self.create_http_response('Default http response if behaviour is not overrriden in child class :)')

    def create_http_response(self, body: Union[str,bytes] = '') -> bytes:
        body = body.encode() if isinstance(body,str) else body
        length = len(body) if body else 0
        headers = (f'HTTP/1.1 200 OK\n'
                f'Content-Type: text/html; charset=UTF-8\n'   
                f'Content-Length: {length}\n\n').encode()
        http_response = headers + body if body else headers
        return http_response

class StaticAssetHandler(HttpBaseHandler):
    def __init__(self, context: Dict[Any,Any]):
        self.full_context = context
        self.static_directory_path = context['staticRoot']
        self.request_should_start_with: List[str] = context['requestsShouldStartWith']
        self.all_files = set(pathlib.Path(self.static_directory_path).glob('**/*')) #get all files in the static directory


    
    def remove_url_prefix(self) -> str:
        for url_part in self.request_should_start_with:
            if self.parsed_http_request.requested_url.startswith(url_part):
                return self.parsed_http_request.requested_url[len(url_part):]
    
    def match_error_response(self) -> str:
        return (f'<pre> you requested for {self.parsed_http_request.requested_url} which does not\n'
                f'start with any of the following {self.request_should_start_with} as set in your settings file. If this\n'
                f'does not match the pattern for static asset requests because it is NOT a static asset request,\n'
                f' you should specify a server to forward non-static-asset requests to in settings.json</pre\n')

    def not_found_error_response(self, absolute_path: str) -> str:
        return (f'<pre> the file requested was searched for in {absolute_path} and it does not exist.\n'
                f'A proper request for a static resource is any of the strings the request should start with (as defined\n'
                f'in your settings.json file) + the relative path to your resource starting from the static_root (defined in\n' 
                f'settings.json). </pre>')

    def handle_request(self, raw_http_request: bytes) -> bytes:
        self.parse_http_request(raw_http_request)
        print(self.parsed_http_request)

        request_matches_pattern = self.parsed_http_request.requested_url.startswith(tuple(self.request_should_start_with))
        if not request_matches_pattern:
            return self.create_http_response(self.match_error_response())

        absolute_path = self.static_directory_path + self.remove_url_prefix() 
        
        if pathlib.Path(absolute_path) in self.all_files:
            static_file_contents = open(absolute_path,'rb').read()
            return self.create_http_response(static_file_contents)
        else:
            return self.create_http_response(self.not_found_error_response(absolute_path))
                
class ManageHandlers:
    """
    picks the handler based on settings and injects the needed context for each handler
    """

    def __init__(self, tasks_and_context: Dict):
        self.tasks_and_context = tasks_and_context
        self.task_to_handler = {'serveStatic':StaticAssetHandler}

    def pick_handlers(self) -> List[HttpBaseHandler]:
        task_handlers: List[HttpBaseHandler] = []
        for task, context in self.tasks_and_context.items():
            if task in self.task_to_handler:
                handlerClass = self.task_to_handler[task]
                task_handlers.append(handlerClass(context))
            else:
                raise NotImplementedError
        return task_handlers