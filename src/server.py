import socket
import threading

from src.constants import (
    SERVER_PORT,
    PROTOCOL_VERSION,
    STATUS_OK,
    STATUS_BAD_REQUEST,
    STATUS_NOT_FOUND,
    STATUS_VERSION_NOT_SUPPORTED,
    METHOD_ADD,
    METHOD_LOOKUP,
    METHOD_LIST,
)
from src.protocol import parse_p2s_request, format_p2s_response
from src.socket_utils import recv_message_text


# In-memory database
peers = {}  # hostname -> upload port
index = []  # list of tuples: (rfc_number, title, hostname, port)
db_lock = threading.Lock()


def _remove_all_for_host(hostname: str):
    global index, peers
    if not hostname:
        return
    with db_lock:
        if hostname in peers:
            del peers[hostname]
        index = [rec for rec in index if rec[2] != hostname]


def _handle_peer(conn: socket.socket, addr):
    announced_host = None
    announced_port = None
    try:
        while True:
            msg = recv_message_text(conn)
            if msg is None:
                break

            req = parse_p2s_request(msg)
            if req is None:
                conn.sendall(format_p2s_response(STATUS_BAD_REQUEST).encode("utf-8"))
                continue

            if req["version"] != PROTOCOL_VERSION:
                conn.sendall(format_p2s_response(STATUS_VERSION_NOT_SUPPORTED).encode("utf-8"))
                continue

            method = req["method"]
            host = req["host"]
            port = req["port"]
            title = req.get("title", "")
            announced_host = host
            announced_port = port
            
            # Log peer connection info on first request
            if method == METHOD_ADD or method == METHOD_LOOKUP or method == METHOD_LIST:
                pass  # Info will be logged with each operation

            if method == METHOD_ADD:
                rfc_number = req["rfc_number"]

                with db_lock:
                    peers[host] = port
                    index[:] = [rec for rec in index if not (rec[0] == rfc_number and rec[2] == host)]
                    index.insert(0, (rfc_number, title, host, port))

                print(f"[server] added RFC {rfc_number}: {title} from {host}:{port}")
                conn.sendall(format_p2s_response(STATUS_OK, [(rfc_number, title, host, port)]).encode("utf-8"))

            elif method == METHOD_LOOKUP:
                rfc_number = req["rfc_number"]
                with db_lock:
                    matches = [rec for rec in index if rec[0] == rfc_number]

                if not matches:
                    conn.sendall(format_p2s_response(STATUS_NOT_FOUND).encode("utf-8"))
                else:
                    conn.sendall(format_p2s_response(STATUS_OK, matches).encode("utf-8"))

            elif method == METHOD_LIST:
                with db_lock:
                    all_records = list(index)
                conn.sendall(format_p2s_response(STATUS_OK, all_records).encode("utf-8"))

            else:
                conn.sendall(format_p2s_response(STATUS_BAD_REQUEST).encode("utf-8"))

    except ConnectionResetError:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
        if announced_host and announced_port:
            print(f"[server] peer {announced_host}:{announced_port} disconnected")
        _remove_all_for_host(announced_host)


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", SERVER_PORT))
    sock.listen()
    print(f"[server] listening on port {SERVER_PORT}")

    while True:
        conn, addr = sock.accept()
        # addr is (ip, port) tuple
        ip, port = addr
        print(f"[server] connection from {ip}:{port}")
        t = threading.Thread(target=_handle_peer, args=(conn, addr), daemon=True)
        t.start()


if __name__ == "__main__":
    main()
