from .http_handlers import HttpBaseHandler, StaticAssetHandler, ReverseProxyHandler, LoadBalancingHandler, HealthCheckHandler
from typing import Dict, Callable, List

class ManageHandlers:
    """
    picks the handler based on settings and injects the needed context and the matching criteria for each handler. A
    callback can additionally be passed in so that any handler that needs it (for updating fields in the server class, for example)
    can get it. This callback is currently only used to update statistics
    """

    def __init__(self, settings: Dict, callback_to_attach: Callable = None):
        self.tasks = settings['tasks']
        self.callback = callback_to_attach
        self.implemented_handlers = {
            'serve_static':StaticAssetHandler,
            'reverse_proxy':ReverseProxyHandler,
            'load_balance':LoadBalancingHandler,
            'health_check':HealthCheckHandler}
    
    def prepare_handlers(self) -> List[HttpBaseHandler]:
        task_handlers: List[HttpBaseHandler] = []
        for task_name, task_info in self.tasks.items():
            match_criteria = task_info['match_criteria']
            needed_context = task_info['context']
            if task_name in self.implemented_handlers:
                handler_class = self.implemented_handlers[task_name]
                task_handlers.append(handler_class(match_criteria, needed_context, self.callback))
            else:
                raise NotImplementedError
        return task_handlers