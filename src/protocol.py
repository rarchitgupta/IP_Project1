"""
Protocol parsing and formatting for P2P-CI
"""

from src.constants import (
    CRLF, PROTOCOL_VERSION, STATUS_PHRASES,
    HEADER_HOST, HEADER_PORT, HEADER_TITLE, HEADER_OS,
    METHOD_ADD, METHOD_LOOKUP, METHOD_LIST, METHOD_GET,
    RFC_ALL, KEYWORD_RFC
)


def _split_message(text: str):
    """
    Split message into (request/status line, headers dict).

    Expects headers end with an empty line.
    """
    # Don't use .strip() here aggressively because it can eat trailing CRLFCRLF.
    lines = text.split(CRLF)

    if not lines or not lines[0].strip():
        return None, None

    first = lines[0].strip()
    headers = {}

    # Header lines until empty line
    for line in lines[1:]:
        if line == "":
            break
        if ":" not in line:
            return None, None
        k, v = line.split(":", 1)
        headers[k.strip()] = v.strip()

    return first, headers


def parse_p2s_request(data: str):
    """
    Parse a P2S request from a string.

    Supported:
      ADD RFC <num> P2P-CI/1.0
      LOOKUP RFC <num> P2P-CI/1.0
      LIST ALL P2P-CI/1.0

    Returns dict or None.
    """
    first, headers = _split_message(data)
    if first is None:
        return None

    parts = first.split()

    if len(parts) == 3 and parts[0] == METHOD_LIST:
        method, who, version = parts
        if who != RFC_ALL:
            return None
        if HEADER_HOST not in headers or HEADER_PORT not in headers:
            return None
        try:
            port = int(headers[HEADER_PORT])
        except ValueError:
            return None
        return {
            "method": method,
            "rfc_number": RFC_ALL,
            "version": version,
            "host": headers[HEADER_HOST],
            "port": port,
            "title": headers.get(HEADER_TITLE, ""),
        }

    if len(parts) == 4:
        method, rfc_kw, rfc_num, version = parts
        if rfc_kw != KEYWORD_RFC:
            return None
        try:
            rfc_number = int(rfc_num)
        except ValueError:
            return None

        if HEADER_HOST not in headers or HEADER_PORT not in headers:
            return None
        try:
            port = int(headers[HEADER_PORT])
        except ValueError:
            return None

        return {
            "method": method,
            "rfc_number": rfc_number,
            "version": version,
            "host": headers[HEADER_HOST],
            "port": port,
            "title": headers.get(HEADER_TITLE, ""),
        }

    return None


def format_p2s_response(status_code: int, rfc_records=None):
    """
    Server response format:

    version <sp> status code <sp> phrase <cr><lf>
    <cr><lf>
    RFC number <sp> RFC title <sp> hostname <sp> upload port number<cr><lf>
    ...
    <cr><lf>
    """
    if rfc_records is None:
        rfc_records = []

    phrase = STATUS_PHRASES.get(status_code, "Unknown")
    out = f"{PROTOCOL_VERSION} {status_code} {phrase}{CRLF}{CRLF}"
    for rfc_num, title, hostname, port in rfc_records:
        out += f"{rfc_num} {title} {hostname} {port}{CRLF}"
    out += CRLF  # final blank line
    return out


def parse_p2p_request(data: bytes):
    """
    Parse a P2P GET request:
      GET RFC <num> P2P-CI/1.0
      Host: ...
      OS: ...
      <blank line>
    """
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        return None

    first, headers = _split_message(text)
    if first is None:
        return None

    parts = first.split()
    if len(parts) != 4:
        return None

    method, rfc_kw, rfc_num, version = parts
    if method != METHOD_GET or rfc_kw != KEYWORD_RFC:
        return None
    try:
        rfc_number = int(rfc_num)
    except ValueError:
        return None

    if HEADER_HOST not in headers or HEADER_OS not in headers:
        return None

    return {
        "method": method,
        "rfc_number": rfc_number,
        "version": version,
        "host": headers[HEADER_HOST],
        "os": headers[HEADER_OS],
    }


def format_p2p_response(status_code: int, headers=None, data=None):
    """
    P2P response:
      P2P-CI/1.0 200 OK
      Date: ...
      ...
      <blank line>
      <raw file bytes>
    """
    if headers is None:
        headers = {}
    if data is None:
        data = b""

    phrase = STATUS_PHRASES.get(status_code, "Unknown")
    out = f"{PROTOCOL_VERSION} {status_code} {phrase}{CRLF}"
    for k, v in headers.items():
        out += f"{k}: {v}{CRLF}"
    out += CRLF
    return out.encode("utf-8") + data


def format_p2s_request(method: str, rfc_number, host: str, port: int, title: str = "") -> str:
    if method == METHOD_LIST:
        first = f"{METHOD_LIST} {RFC_ALL} {PROTOCOL_VERSION}{CRLF}"
    else:
        first = f"{method} {KEYWORD_RFC} {rfc_number} {PROTOCOL_VERSION}{CRLF}"

    out = first
    out += f"{HEADER_HOST}: {host}{CRLF}"
    out += f"{HEADER_PORT}: {port}{CRLF}"
    if method in (METHOD_ADD, METHOD_LOOKUP):
        out += f"{HEADER_TITLE}: {title}{CRLF}"
    out += CRLF
    return out


def parse_p2s_response(text: str):
    lines = text.split(CRLF)
    if not lines or not lines[0].strip():
        return None, []

    status_line = lines[0].split()
    if len(status_line) < 2:
        return None, []

    try:
        status_code = int(status_line[1])
    except ValueError:
        return None, []

    try:
        blank_idx = lines.index("")
    except ValueError:
        return status_code, []

    records = []
    for line in lines[blank_idx + 1 :]:
        if line == "":
            break
        parts = line.split()
        if len(parts) < 3:
            continue
        rfc = int(parts[0])
        port = int(parts[-1])
        host = parts[-2]
        title = " ".join(parts[1:-2])
        records.append((rfc, title, host, port))

    return status_code, records
