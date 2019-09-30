
from utils import HttpRequest, HttpResponse
import pathlib
from typing import Any, List, Dict, Union, Sequence

class HttpBaseHandler:

    def should_handle(self, http_request: HttpRequest) -> bool:
        """ Determines whether the handler for a certain task (like serving static files) should handle
            the given request. For example in your settings.json file you """
        for target_http_request_attribute, required_attribute_values in self.http_request_match_criteria.items():
            actual_request_attribute_value = http_request[target_http_request_attribute]
            
            if target_http_request_attribute == 'url':
                #url matching is different because you are not checking for the simple existance of the
                #request value in the required values.
                if not actual_request_attribute_value.startswith(tuple(required_attribute_values)):
                    return False
            else:
                if actual_request_attribute_value not in required_attribute_values:
                    return False
    
        self.http_request = http_request
        return True

    def handle_request(self) -> bytes:
        return HttpResponse(body='Default http response if behaviour is not overrriden in child class :)').dump()


class StaticAssetHandler(HttpBaseHandler):
    def __init__(self, match_criteria: Dict[str, List], context: Dict[str, str]):
        self.http_request_match_criteria = match_criteria
        self.static_directory_path = context['staticRoot']
        self.all_files = set(pathlib.Path(self.static_directory_path).glob('**/*')) #get all files in the static directory

  
    def not_found_error_response(self, absolute_path: str) -> str:
        return (f'<pre> the file requested was searched for in {absolute_path} and it does not exist.\n'
                f'A proper request for a static resource is any of the strings the request should start with (as defined\n'
                f'in your settings.json file) + the relative path to your resource starting from the static_root (defined in\n' 
                f'settings.py). </pre>')

    def remove_url_prefix(self) -> str:
        for required_beginning in self.http_request_match_criteria['url']:
            if self.http_request.requested_url.startswith(required_beginning):
                return self.http_request.requested_url[len(required_beginning):]
        
    def handle_request(self) -> bytes:
        absolute_path = self.static_directory_path + self.remove_url_prefix() 
        
        if pathlib.Path(absolute_path) in self.all_files:
            static_file_contents = open(absolute_path,'rb').read()
            return HttpResponse(body=static_file_contents).dump()
        else:
            return HttpResponse(response_code=400, body=self.not_found_error_response(absolute_path)).dump()

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