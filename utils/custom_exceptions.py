class ClientClosingConnection(Exception):
    """ 
    This exception is thrown in the cases where the client sends over an empty byte string (b'') which means
    the client is closing its side of the connection
    """

class NotValidHttpFormat(Exception):
    """
    This exception is thrown when a client sends over bytes that
    don't follow the http spec.
    """