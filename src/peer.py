import argparse
import os
import platform
import socket
import threading
from datetime import datetime, timezone

from src.constants import (
    SERVER_PORT,
    BUFFER_SIZE,
    CRLF,
    PROTOCOL_VERSION,
    STATUS_OK,
    STATUS_NOT_FOUND,
    STATUS_BAD_REQUEST,
    STATUS_VERSION_NOT_SUPPORTED,
    HEADER_DATE,
    HEADER_OS,
    HEADER_LAST_MODIFIED,
    HEADER_CONTENT_LENGTH,
    HEADER_CONTENT_TYPE,
    METHOD_ADD,
    METHOD_LOOKUP,
    METHOD_LIST,
)
from src.protocol import parse_p2p_request, format_p2p_response, format_p2s_request, parse_p2s_response
from src.socket_utils import recv_until_marker, recv_p2s_response


def http_date(ts=None) -> str:
    if ts is None:
        dt = datetime.now(timezone.utc)
    else:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def read_p2s_response(sock: socket.socket) -> str:
    buf = recv_p2s_response(sock)
    return buf.decode("utf-8", errors="replace")


def find_local_rfcs(peer_dir: str):
    """
    Looks for files named like rfc123.txt (case-insensitive).
    Returns list of (rfc_number, title, filepath).
    Title is either the first non-empty line or a fallback.
    """
    rfcs = []
    if not os.path.isdir(peer_dir):
        return rfcs

    for name in os.listdir(peer_dir):
        lower = name.lower()
        if not (lower.startswith("rfc") and lower.endswith(".txt")):
            continue
        num_part = lower[3:-4]
        if not num_part.isdigit():
            continue
        rfc_number = int(num_part)
        path = os.path.join(peer_dir, name)

        title = f"RFC {rfc_number}"
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        title = line[:80]
                        break
        except Exception:
            pass

        rfcs.append((rfc_number, title, path))

    return sorted(rfcs, key=lambda x: x[0])


class UploadServer:
    def __init__(self, peer_dir: str):
        self.peer_dir = peer_dir
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", 0))
        self.sock.listen()
        self.port = self.sock.getsockname()[1]
        self.running = True

    def start(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass

    def _loop(self):
        print(f"[peer] upload server listening on port {self.port}")
        while self.running:
            try:
                conn, addr = self.sock.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn, addr), daemon=True).start()

    def _handle(self, conn: socket.socket, addr):
        try:
            raw = recv_until_marker(conn, b"\r\n\r\n")
            if raw is None:
                return

            req = parse_p2p_request(raw)
            if req is None:
                conn.sendall(format_p2p_response(STATUS_BAD_REQUEST, headers={"Content-Length": "0"}, data=b""))
                return

            if req["version"] != PROTOCOL_VERSION:
                conn.sendall(format_p2p_response(STATUS_VERSION_NOT_SUPPORTED, headers={"Content-Length": "0"}, data=b""))
                return

            rfc_number = req["rfc_number"]
            path = os.path.join(self.peer_dir, f"rfc{rfc_number}.txt")
            if not os.path.exists(path):
                conn.sendall(format_p2p_response(STATUS_NOT_FOUND, headers={"Content-Length": "0"}, data=b""))
                return

            with open(path, "rb") as f:
                data = f.read()

            st = os.stat(path)
            headers = {
                HEADER_DATE: http_date(),
                HEADER_OS: platform.platform(),
                HEADER_LAST_MODIFIED: http_date(st.st_mtime),
                HEADER_CONTENT_LENGTH: str(len(data)),
                HEADER_CONTENT_TYPE: "text/plain",
            }
            conn.sendall(format_p2p_response(STATUS_OK, headers=headers, data=data))

        finally:
            try:
                conn.close()
            except Exception:
                pass


def download_rfc(from_host: str, from_port: int, rfc_number: int, save_path: str) -> tuple[bool, bytes]:
    s = socket.create_connection((from_host, from_port), timeout=10)
    try:
        req = (
            f"GET RFC {rfc_number} {PROTOCOL_VERSION}{CRLF}"
            f"Host: {from_host}{CRLF}"
            f"OS: {platform.platform()}{CRLF}"
            f"{CRLF}"
        )
        s.sendall(req.encode("utf-8"))

        buf = recv_until_marker(s, b"\r\n\r\n")
        if buf is None or b"\r\n\r\n" not in buf:
            return False, b""

        header_bytes, rest = buf.split(b"\r\n\r\n", 1)
        header_text = header_bytes.decode("utf-8", errors="replace")
        header_lines = header_text.split(CRLF)

        status_parts = header_lines[0].split()
        if len(status_parts) < 2:
            return False, b""
        try:
            status_code = int(status_parts[1])
        except ValueError:
            return False, b""
        if status_code != 200:
            return False, b""

        headers = {}
        for line in header_lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()

        length = int(headers.get("Content-Length", "0"))
        data = rest
        while len(data) < length:
            chunk = s.recv(BUFFER_SIZE)
            if not chunk:
                break
            data += chunk

        data = data[:length]
        with open(save_path, "wb") as f:
            f.write(data)

        return True, data
    finally:
        s.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-host", default="127.0.0.1")
    parser.add_argument("--peer-dir", required=True)
    parser.add_argument("--hostname", default=socket.getfqdn())
    args = parser.parse_args()

    os.makedirs(args.peer_dir, exist_ok=True)

    upload = UploadServer(args.peer_dir)
    upload.start()

    # Connect to central server
    server_sock = socket.create_connection((args.server_host, SERVER_PORT))
    print(f"[peer] connected to server {args.server_host}:{SERVER_PORT}")

    my_host = args.hostname
    my_port = upload.port

    # Register local RFCs
    local = find_local_rfcs(args.peer_dir)
    if local:
        print("[peer] registering local RFCs with server...")
    for rfc_number, title, _path in local:
        print(f"[peer] registering RFC {rfc_number}: {title}")
        req = format_p2s_request("ADD", rfc_number, my_host, my_port, title)
        server_sock.sendall(req.encode("utf-8"))
        resp = read_p2s_response(server_sock)
        print(resp.strip())

    # Simple CLI
    print("\nCommands:")
    print("  list")
    print("  lookup <rfc>")
    print("  get <rfc>")
    print("  quit\n")

    try:
        while True:
            cmd = input("p2p> ").strip()
            if not cmd:
                continue
            if cmd == "quit":
                break

            if cmd == "list":
                req = format_p2s_request(METHOD_LIST, "ALL", my_host, my_port, "")
                server_sock.sendall(req.encode("utf-8"))
                resp = read_p2s_response(server_sock)
                # Print response, removing only trailing whitespace to preserve status line
                print(resp.rstrip())
                continue

            if cmd.startswith("lookup "):
                parts = cmd.split()
                if len(parts) != 2 or not parts[1].isdigit():
                    print("Usage: lookup <rfc_number>")
                    continue
                rfc = int(parts[1])
                req = format_p2s_request(METHOD_LOOKUP, rfc, my_host, my_port, f"RFC {rfc}")
                server_sock.sendall(req.encode("utf-8"))
                resp = read_p2s_response(server_sock)
                # Print response, removing only trailing whitespace to preserve status line
                print(resp.rstrip())
                continue

            if cmd.startswith("get "):
                parts = cmd.split()
                if len(parts) != 2 or not parts[1].isdigit():
                    print("Usage: get <rfc_number>")
                    continue
                rfc = int(parts[1])

                req = format_p2s_request(METHOD_LOOKUP, rfc, my_host, my_port, f"RFC {rfc}")
                server_sock.sendall(req.encode("utf-8"))
                resp = read_p2s_response(server_sock)
                status, records = parse_p2s_response(resp)

                if status != 200 or not records:
                    print(resp.strip())
                    continue

                chosen = None
                chosen_title = None
                for rr, title, host, port in records:
                    if host != my_host or port != my_port:
                        chosen = (host, port)
                        chosen_title = title
                        break

                if chosen is None:
                    print("[peer] only you have this RFC already (or server only returned you).")
                    continue

                host, port = chosen
                save_path = os.path.join(args.peer_dir, f"rfc{rfc}.txt")
                print(f"[peer] downloading RFC {rfc} from {host}:{port} ...")
                ok, _data = download_rfc(host, port, rfc, save_path)

                if not ok:
                    print("[peer] download failed")
                    continue

                print(f"[peer] saved to {save_path}")

                req = format_p2s_request(METHOD_ADD, rfc, my_host, my_port, chosen_title or f"RFC {rfc}")
                server_sock.sendall(req.encode("utf-8"))
                resp2 = read_p2s_response(server_sock)
                print(resp2.strip())
                continue

            print("Unknown command. Try: list | lookup <rfc> | get <rfc> | quit")

    finally:
        try:
            server_sock.close()
        except Exception:
            pass
        upload.stop()
        print("[peer] exited.")


if __name__ == "__main__":
    main()
