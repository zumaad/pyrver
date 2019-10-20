
![logo](static/images/pyrverlogo.png)

(i made a logo because there isn't anything visual about this project)

This is an http server written in python using the lowest level networking library (I think) so I could try building an http server "from scatch".

The server should be able to accept http requests and give back http responses, all adhering to the http spec so that any client (like a browser) can communicate with it.

Because I don't want to simply return an "ok" http response everytime a client makes a request, I'm brainstorming some cool things to do with the request before returning a reponse. My current idea is try to implement some of the stuff nginx has such as load balancing, acting as a reverse proxy, caching, handling TLS/SSL, being able to serve files from a directory, streaming, blocking abusive clients, routing based on hostname, etc.


___
on settings.json
"tasks":{
        "serve_static":{
                "staticRoot":"/Users/zumaad/httpserver/static/",
                "requestsShouldStartWith":["/static/","/whatever/","/assets/"]
            } 
    }    

The reason i need the "requestsShouldStartWith" field for serving static assets is because if i use this like nginx
where static files are served from nginx and other requests are just sent downstream to other servers, there needs
to be a way to decide between which requests this server should serve directly and which ones it should send. Otherwise, there isn't a significant reason to use this other than your urls looking better(?). 