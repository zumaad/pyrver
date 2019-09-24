
from utils import HttpRequest
import pathlib
from typing import Any, List, Dict, Union, Sequence

class HttpBaseHandler:

    def should_handle(self, http_request: HttpRequest) -> bool:
        for target_http_request_attribute, required_attribute_values in self.http_request_match_criteria.items():
            actual_request_attribute_value = http_request[target_http_request_attribute]
            
            if target_http_request_attribute == 'url':
                if not actual_request_attribute_value.startswith(tuple(required_attribute_values)):
                    return False
            else:
                if actual_request_attribute_value not in required_attribute_values:
                    return False
    
        self.http_request = http_request
        return True

    def handle_request(self) -> bytes:
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
    def __init__(self, match_criteria: Dict[str, List], context: Dict[str, str]):
        self.http_request_match_criteria = match_criteria
        self.static_directory_path = context['staticRoot']
        self.all_files = set(pathlib.Path(self.static_directory_path).glob('**/*')) #get all files in the static directory

  
    def not_found_error_response(self, absolute_path: str) -> str:
        return (f'<pre> the file requested was searched for in {absolute_path} and it does not exist.\n'
                f'A proper request for a static resource is any of the strings the request should start with (as defined\n'
                f'in your settings.json file) + the relative path to your resource starting from the static_root (defined in\n' 
                f'settings.json). </pre>')

    def remove_url_prefix(self) -> str:
        for required_beginning in self.http_request_match_criteria['url']:
            if self.http_request.requested_url.startswith(required_beginning):
                return self.http_request.requested_url[len(required_beginning):]
        
   
    def handle_request(self) -> bytes:
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

    def __init__(self, settings: Dict):
        self.tasks = settings['tasks']
        print(self.tasks)
        self.implemented_handlers = {'serveStatic':StaticAssetHandler}
    
    def pick_handlers(self) -> List[HttpBaseHandler]:
        task_handlers: List[HttpBaseHandler] = []
        for task_name, task_info in self.tasks.items():
            match_criteria = task_info['matchCriteria']
            needed_context = task_info['context']
            if task_name in self.implemented_handlers:
                handlerClass = self.implemented_handlers[task_name]
                task_handlers.append(handlerClass(match_criteria, needed_context))
            else:
                raise NotImplementedError
        return task_handlers