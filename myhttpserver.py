import socket
import time
import argparse
from time import sleep

def http_parser(http_message):
    # print(http_message.split('\n'))
    print(http_message)
    

def create_http_response(body):
    if not body:
        length = 0
    else:
        length = len(body)
    
    headers = (f'HTTP/1.1 200 OK\n'
               f'Content-Type: text/html; charset=UTF-8\n'   
               f'Content-Length: {length}\n\n').encode()
    if body:
        return headers + body
    else:
         return headers



parser = argparse.ArgumentParser()
parser.add_argument('port')
args = parser.parse_args()

with open('home.html','rb') as home_page:
    home_page_html = home_page.read()

HOST = '0.0.0.0'  # Standard loopback interface address (localhost)
PORT = int(args.port)   # Port to listen on (non-privileged ports are > 1023)

listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listening_socket.bind((HOST, PORT))
listening_socket.listen()
print("listening")
client_socket, addr = listening_socket.accept()
print('accepted client')
sleep(5)
while True:
    http_message = client_socket.recv(1024)
    print(http_message)
    if b'GET' in http_message:
        print(http_message.decode())
        http_response = create_http_response(home_page_html) 
        
        client_socket.sendall(http_response)
    elif b'POST' in http_message:
        print(http_message.decode())
        print(client_socket.recv(100))
        print("past last recv")

        http_response = create_http_response(None) 
        client_socket.sendall(http_response)
    elif not http_message:
        print(http_message)
        print("client closing connection")
        break
