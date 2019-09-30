settings = {
    "tasks":{
        "serve_static":{
            "match_criteria": {
                "port":[str(port_num) for port_num in range(3330,3335)], 
                "host": ["testingserver.com","localhost","testingserver.com2"], 
                "url":["/static/"]
                              },
            "context": {"staticRoot":"/Users/zumaad/httpserver/static/"}
        },
        "proxy": {
            "match_criteria": {
                "host":["testingserver2.com"]
                },
            "context": {'send_to':['localhost:4000']}
        }
    }  
}