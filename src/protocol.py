"""
Protocol parsing and formatting for P2P-CI
"""

from src.constants import CRLF, PROTOCOL_VERSION, STATUS_PHRASES


def parse_p2s_request(data: str):
    """
    Parse a P2S request from a string.
    
    Returns dict with keys: method, rfc_number, host, port, title
    Returns None if parsing fails.
    """
    lines = data.strip().split(CRLF)
    if len(lines) < 3:
        return None
    
    # Parse request line: "ADD RFC 123 P2P-CI/1.0"
    request_line = lines[0].split()
    if len(request_line) != 3:
        return None
    
    method, rfc_spec, version = request_line
    
    # Extract RFC number from "RFC 123"
    if not rfc_spec.startswith("RFC "):
        return None
    rfc_number = rfc_spec[4:]
    
    # Parse headers
    headers = {}
    for line in lines[1:]:
        if not line:  # Empty line = end of headers
            break
        if ":" not in line:
            return None
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()
    
    # Extract required headers
    if "Host" not in headers or "Port" not in headers:
        return None
    
    try:
        port = int(headers["Port"])
    except ValueError:
        return None
    
    return {
        "method": method,
        "rfc_number": rfc_number,
        "version": version,
        "host": headers["Host"],
        "port": port,
        "title": headers.get("Title", ""),
    }


def format_p2s_response(status_code: int, rfc_records=None):
    """
    Format a P2S response.
    
    rfc_records: list of (rfc_number, title, hostname, port) tuples
    Returns formatted response string.
    """
    if rfc_records is None:
        rfc_records = []
    
    phrase = STATUS_PHRASES.get(status_code, "Unknown")
    response = f"{PROTOCOL_VERSION} {status_code} {phrase}{CRLF}"
    response += CRLF
    
    for rfc_num, title, hostname, port in rfc_records:
        response += f"{rfc_num} {title} {hostname} {port}{CRLF}"
    
    response += CRLF
    return response


def parse_p2p_request(data: bytes):
    """
    Parse a P2P GET request from bytes.
    
    Returns dict with keys: method, rfc_number, host, os
    Returns None if parsing fails.
    """
    try:
        text = data.decode()
    except UnicodeDecodeError:
        return None
    
    lines = text.strip().split(CRLF)
    if len(lines) < 3:
        return None
    
    # Parse request line: "GET RFC 1234 P2P-CI/1.0"
    request_line = lines[0].split()
    if len(request_line) != 3:
        return None
    
    method, rfc_spec, version = request_line
    
    if not rfc_spec.startswith("RFC "):
        return None
    
    try:
        rfc_number = int(rfc_spec[4:])
    except ValueError:
        return None
    
    # Parse headers
    headers = {}
    for line in lines[1:]:
        if not line:
            break
        if ":" not in line:
            return None
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()
    
    if "Host" not in headers or "OS" not in headers:
        return None
    
    return {
        "method": method,
        "rfc_number": rfc_number,
        "version": version,
        "host": headers["Host"],
        "os": headers["OS"],
    }


def format_p2p_response(status_code: int, headers=None, data=None):
    """
    Format a P2P response into bytes.
    
    headers: dict of header name -> value
    data: file content as bytes
    Returns complete response as bytes.
    """
    if headers is None:
        headers = {}
    if data is None:
        data = b""
    
    phrase = STATUS_PHRASES.get(status_code, "Unknown")
    response = f"{PROTOCOL_VERSION} {status_code} {phrase}{CRLF}"
    
    for key, value in headers.items():
        response += f"{key}: {value}{CRLF}"
    
    response += CRLF
    
    return response.encode() + data
