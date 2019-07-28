This is an http server written in python using the lowest level networking library (I think) so I could try building an http server "from scatch".

The server should be able to accept http requests and give back http responses, all adhering to the http spec so that any client (like a browser) can communicate with it.

Because I don't want to simply return an "ok" http response everytime a client makes a request, I'm brainstorming some cool things to do with the request before returning a reponse. Current ideas are:

1. point the server to a directory and be able to serve files from the directory

2. make it WSGI compliant, so I can point to a WSGI compliant web framework like Django or Flask and be able to use it instead of the default development web server that comes with Django or Flask.

3. make my own web framework and have my web server communicate with it through a specification/interface I made (not WSGI)

Things that I want to work on that don't have to do with returning http responses are: being able to accept multiple connections at the same time, be able to serve contents at a really high rate, maybe using multi threading or asyncio :).