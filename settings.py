from typing import Dict

#think about settings order, if there is a task with a unrestrictive match criteria and its before
#another task with restrictive match criteria and there is overlap, the first task will swallow
#all the requests even though thats not the user's intended behaviour. For example, lets say there are two
#tasks: serve_static and reverse proxy. They both have matching criteria that includes a check for the 
#host name which should be gooby.com. But serve static has an additional matching criteria which checks
#for the url and it should be prefixed with /static/. If the reverse_proxy handler gets checked first, then
#it will handle the request even if the url is prefixed with /static/ as long as the host is gooby.com. One easy
#fix is to have some ordering where the handlers for tasks with the most restrictive criteria are checked first.

settings = {
    "tasks":{

        "serve_static":{
            "match_criteria": {
                "port":['9999'], 
                "host": ["testingserver.com","localhost","testingserver2.com"], 
                "url":["/static/"]
                              },
            "context": {"staticRoot":"/Users/zumaad/httpserver/static/"}
        },

        "reverse_proxy": {
            "match_criteria": {
                "url": ["/reverseproxy/"]
                },
            "context": {
                'send_to':('localhost',5000)
                }
        },

        "load_balance": {
            "match_criteria": {
                "host":["testingserver2.com"]
                },
            "context": { 
                'send_to':
                    [('localhost', 4000), ('localhost', 4500)],
                "strategy":"round_robin"
                }
        },

        # "load_balance": {
        #     "match_criteria": {
        #         "url":["/testweighted/"]
        #     },
        #     "context": {
        #         "send_to":
        #             [('localhost', 4000, 1/4), ('localhost', 4500, 1/4), ('localhost', 5000, 2/4)],
        #         "strategy":"weighted"
        #     }
        # },

        "health_check": {
            "match_criteria": {"url":['/health/']},
            "context":{}
        }
    }  
}
#the diff between load_balance and reverse_proxy is that in reverse_proxy u can only specify one server as there is
#no concept of reverse proxying to multiple servers at once. Furthermore, in load balancing u can specify types of load
#balancing like round robin or weighted. 
#i could make it such that if you specified multiple servers in reverse_proxy it assumes u want to load balance, but this
#estabalishes a clearer distinction between the two.


settings2 = {
    "tasks":{
        "health_check": {
            "match_criteria": {},
            "context": {}
        }
    }  
}

settings_map: Dict[int,Dict] = {
    1:settings,
    2:settings2
}