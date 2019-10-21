class TcpHandler:
    def __init__(self):
        pass

    def should_handle(self, tcp_data: bytes) -> bool:
        pass

    def handle_request(self, tcp_data: bytes) -> bytes:
        pass