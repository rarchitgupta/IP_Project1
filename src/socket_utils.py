"""
Socket utilities for reading protocol messages
"""

import socket
from src.constants import BUFFER_SIZE, CRLF


def recv_until_marker(sock: socket.socket, marker: bytes = b"\r\n\r\n") -> bytes | None:
    """
    Read from socket until marker is found.
    Returns bytes up to and including marker, or None if connection closed.
    """
    buf = b""
    while True:
        chunk = sock.recv(BUFFER_SIZE)
        if not chunk:
            return None
        buf += chunk
        if marker in buf:
            return buf


def recv_message_text(sock: socket.socket) -> str | None:
    """
    Read a complete message (headers + blank line) and return as text.
    Returns None if connection closed.
    """
    buf = recv_until_marker(sock, b"\r\n\r\n")
    if buf is None:
        return None
    return buf.decode("utf-8", errors="replace")


def recv_p2s_response(sock: socket.socket) -> bytes:
    """
    Read a P2S response which ends with blank line after data.
    Returns complete response as bytes (may be empty if connection closes).
    """
    buf = b""

    # Read until first CRLFCRLF (end of status line and headers)
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(BUFFER_SIZE)
        if not chunk:
            return buf
        buf += chunk

    head, rest = buf.split(b"\r\n\r\n", 1)

    # Read until we see CRLFCRLF again (blank line after data)
    # Note: For responses with no records (like 404), rest may already be just "\r\n"
    # In that case, we should return immediately instead of blocking.
    while b"\r\n\r\n" not in rest:
        # Check if rest is just a blank line (empty record section)
        if rest == b"\r\n":
            return head + b"\r\n\r\n" + rest
        
        chunk = sock.recv(BUFFER_SIZE)
        if not chunk:
            break
        rest += chunk

    return head + b"\r\n\r\n" + rest
