settings = {
    "tasks":{
        "serveStatic":{
            "matchCriteria": {"port":[str(port_num) for port_num in range(3330,3335)], 
                              "host": ["testingserver.com","localhost","testingserver2.com"], 
                              "url":["/static/"]
                              },
            "context": {"staticRoot":"/Users/zumaad/httpserver/static/"}
        }
    }  
}