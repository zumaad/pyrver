
import logging
import argparse
import json
from server.thread_per_client_server import ThreadPerClient
from server.thread_per_request_server import ThreadPerRequest
from utils.general_utils import settings_analyzer,settings_preparer
from settings import settings_map


logging.basicConfig(filename='server.log',
                            filemode='a',
                            datefmt='%H:%M:%S',
                            level=logging.DEBUG)
parser = argparse.ArgumentParser()
parser.add_argument('--settings','-s',type=int)
parser.add_argument('--type','-t',type=str)
args = parser.parse_args() 


def main() -> None:
    type_to_server_mapping = {
        '1':ThreadPerClient,
        '2':ThreadPerRequest,
        'ThreadPerClient':ThreadPerClient,
        'ThreadPerRequest':ThreadPerRequest,
        'tpc':ThreadPerClient,
        'tpr':ThreadPerRequest
    }
    settings = settings_analyzer(settings_preparer(settings_map[args.settings]))
    server_impl = type_to_server_mapping[args.type]
    print(json.dumps(settings,default=str,sort_keys=True, indent=2))
    server = server_impl(settings)
    try:
        server.start_loop()
    except KeyboardInterrupt:
        print("Stopping server :(")
        server.stop_loop()

if __name__ == "__main__":
    main()