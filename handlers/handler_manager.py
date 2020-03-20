from .http_handlers import HttpBaseHandler, StaticAssetHandler, ReverseProxyHandler, LoadBalancingHandler, HealthCheckHandler, AsyncReverseProxyHandler, AsyncLoadBalancingHandler
from typing import Dict, Callable, List

class ManageHandlers:
    """
    picks the handler based on settings and injects the needed context and the matching criteria for each handler. A
    callback can additionally be passed in so that any handler that needs it (for updating fields in the server class, for example)
    can get it. 
    """

    def __init__(self, settings: Dict, server_obj):
        self.tasks = settings['tasks']
        self.server_obj = server_obj
        self.implemented_handlers = {
            'serve_static':StaticAssetHandler,
            'reverse_proxy':ReverseProxyHandler,
            'load_balance':LoadBalancingHandler,
            'health_check':HealthCheckHandler}
        
        self.sync_compatible = {
            'serve_static':StaticAssetHandler,
            'reverse_proxy':AsyncReverseProxyHandler,
            'load_balance':AsyncLoadBalancingHandler,
            'health_check':HealthCheckHandler
        }
    
    def prepare_handlers(self) -> List[HttpBaseHandler]:
        """
        Picks handlers based on the settings and the server type as the async server has some 
        different handlers and not picking all the handlers also means less iterations through handlers
        when checking which one is supposed to handle the incoming http request.
        """
        compatible_handlers = self.sync_compatible if self.server_obj.get_type() == 'sync' else self.implemented_handlers
        task_handlers: List[HttpBaseHandler] = []
        for task_name, task_info in self.tasks.items():
            match_criteria = task_info['match_criteria']
            needed_context = task_info['context']
            if task_name in compatible_handlers:
                handler_class = compatible_handlers[task_name]
                task_handlers.append(handler_class(match_criteria, needed_context, self.server_obj))
            else:
                raise NotImplementedError
        return task_handlers