from typing import Dict

settings = {
    "tasks":{

        "serve_static":{
            "match_criteria": {
                "port":[str(port_num) for port_num in range(3330,3335)], 
                "host": ["testingserver.com","localhost","testingserver2.com"], 
                "url":["/static/"]
                              },
            "context": {"staticRoot":"/Users/zumaad/httpserver/static/"}
        },

        "reverse_proxy": {
            "match_criteria": {
                "host":["testingserver3.com"]
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