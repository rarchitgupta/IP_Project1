"""
Constants for P2P-CI system
"""

# Network
SERVER_PORT = 7734
BUFFER_SIZE = 4096

# Protocol
PROTOCOL_VERSION = "P2P-CI/1.0"
CRLF = "\r\n"

# Status Codes
STATUS_OK = 200
STATUS_BAD_REQUEST = 400
STATUS_NOT_FOUND = 404
STATUS_VERSION_NOT_SUPPORTED = 505

STATUS_PHRASES = {
    200: "OK",
    400: "Bad Request",
    404: "Not Found",
    505: "P2P-CI Version Not Supported",
}

# Methods
METHOD_ADD = "ADD"
METHOD_LOOKUP = "LOOKUP"
METHOD_LIST = "LIST"
METHOD_GET = "GET"

# Headers
HEADER_HOST = "Host"
HEADER_PORT = "Port"
HEADER_TITLE = "Title"
HEADER_OS = "OS"
HEADER_DATE = "Date"
HEADER_CONTENT_LENGTH = "Content-Length"
HEADER_CONTENT_TYPE = "Content-Type"
HEADER_LAST_MODIFIED = "Last-Modified"
