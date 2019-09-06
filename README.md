This is an http server written in python using the lowest level networking library (I think) so I could try building an http server "from scatch".

The server should be able to accept http requests and give back http responses, all adhering to the http spec so that any client (like a browser) can communicate with it.

Because I don't want to simply return an "ok" http response everytime a client makes a request, I'm brainstorming some cool things to do with the request before returning a reponse. My current idea is try to implement some of the stuff nginx has such as load balancing, being able to serve files from a directory, etc.
