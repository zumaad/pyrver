
import logging
import argparse
import json
from server.thread_per_client_server import PurelyThreadedServer
from server.thread_per_request_server import Server
from utils.general_utils import settings_analyzer,settings_preparer
from settings import settings_map


logging.basicConfig(filename='server.log',
                            filemode='a',
                            datefmt='%H:%M:%S',
                            level=logging.DEBUG)
parser = argparse.ArgumentParser()
parser.add_argument('--settings','-s',type=int)
args = parser.parse_args() 


def main() -> None:
    settings = settings_analyzer(settings_preparer(settings_map[args.settings]))
    print(json.dumps(settings,default=str,sort_keys=True, indent=2))
    # server = Server(settings, port = args.port)
    server = PurelyThreadedServer(settings)
    try:
        server.start_loop()
    except KeyboardInterrupt:
        print("Stopping server :(")
        server.stop_loop()

if __name__ == "__main__":
    main()