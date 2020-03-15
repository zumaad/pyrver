import selectors
from typing import Callable, Union, Generator
import datetime
import socket

class ResourceTask:
    """ 
    A resource task is a task that is dependent on a file like object (socket or actual file for example) to 
    be readable or writable. A coroutine will yield this type of task so that it can be resumed by the event loop when
    the file like object is readable or writable. For example, lets say that you have a coroutine that is making a server request
    and needs to wait for the response
    The server could take a long time to send the response, and you want to be able to do other things during that time. So, the
    function just has to yield event_loop.resource_task(socket_that_communicates_with_server, 'readable'). The coroutine will then be paused
    and the event loop will run other coroutines. When the event loop notices that the 'socket_that_communicates_with_server' is 
    readable (meaning it has data in it), then the couroutine associated with the task will be resumed. 

    This ResourceTask class is never called explicitly by the coroutines, the coroutines use the 'resource_task' method on the 
    EventLoop class to create a ResourceTask which they then yield.
    """
    EVENT_TO_SELECTORS_EVENT = {
        #selectors.EVENT_WRITE and EVENT_READ are just ints, but its better to use the variable names.
        'writable':selectors.EVENT_WRITE,
        'readable':selectors.EVENT_READ 
    }

    def __init__(self, resource, event: str):
        """
        a event such as writable or readable along with a resource such as a socket or a file is provided. The resource is registered
        with the event loop so that the event loop can store it in a Selector which it uses to monitor which resources are ready to give back
        to the coroutine that yielded them.
        """
        self.resource = resource
        
        try:
            self.event = self.EVENT_TO_SELECTORS_EVENT[event]
        except KeyError:
            raise KeyError(f"you did not provide a valid event associated with this resource task. Valid events are {self.EVENT_TO_SELECTORS_EVENT}")

    def __str__(self):
        return str(vars(self))
    
class TimedTask:
    """
    A TimedTask is simply used to pause a coroutine for the given delay. The coroutine that 
    yielded the TimedTask will be resumed after the timedtask is complete.
    """
    def __init__(self, delay: int):
        self.delay = delay
        self.delay_time = datetime.timedelta(seconds=delay)
        self.start_time = datetime.datetime.now()
        self.end_time = self.start_time + self.delay_time
        
    def __str__(self):
        return str(vars(self))

class EventLoop:
    """
    The great event loop. This class is responsible for running coroutines, getting tasks from them, 
    checking whether the tasks are complete, and then resuming the coroutines and passing in 
    any resources the coroutines may need.
    """

    def __init__(self):
        self.task_to_coroutine = {}
        self.ready_resources = set()
        self.resource_selector = selectors.DefaultSelector()
        
    def register_resource(self, resource, event: int):
        self.resource_selector.register(resource, event)
    
    def deregister_resource(self, resource) -> None:
        for task in self.task_to_coroutine:
            if task.resource == resource:
                del self.task_to_coroutine[task]
                break

    def run_coroutine(self, func: Callable, *func_args):
        coroutine = func(*func_args)
        task = next(coroutine)
        if task:
            self.task_to_coroutine[task] = coroutine
            if isinstance(task, ResourceTask):
                self.register_resource(task.resource, task.event)
    
    def is_complete(self, task) -> bool:
        if isinstance(task, ResourceTask):
            return self.is_resource_task_complete(task)
        elif isinstance(task, TimedTask):
            return self.is_timed_task_complete(task)
        else:
            raise ValueError(f"task has to be either a resource task or a timed task, got {str(task)}")
    
    def is_resource_task_complete(self, resource_task: ResourceTask) -> bool:
        return resource_task.resource in self.ready_resources
    
    def is_timed_task_complete(self, timed_task: TimedTask) -> bool:
        return datetime.datetime.now() > timed_task.end_time

    
    def get_new_task(self, coroutine: Generator, task):
        if isinstance(task, ResourceTask):
            self.resource_selector.unregister(task.resource)

        try:
            new_task = coroutine.send(True)
            return new_task
        except StopIteration:
            return None

    def loop(self):
        """
        This is the meat of the event loop. 
        """
        self.ready_resources = set(self.resource_selector.select(-1))
        while True:
            for task, coroutine in list(self.task_to_coroutine.items()):
                if self.is_complete(task):
                    new_task = self.get_new_task(coroutine, task)
                    del self.task_to_coroutine[task]
                    
                    if new_task:
                        self.task_to_coroutine[new_task] = coroutine
                        if isinstance(task, ResourceTask):
                            self.register_resource(task.resource, task.event)
            if not self.task_to_coroutine:
                print("all tasks are over, exiting the loop")
                break

            self.ready_resources = set(resource_wrapper.fileobj for resource_wrapper, event in self.resource_selector.select(-1))



