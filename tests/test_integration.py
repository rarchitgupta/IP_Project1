"""
Integration tests for P2P-CI system.

End-to-end tests with real server, peers, file I/O, and network operations.
Tests the complete workflow: registration, upload server, downloads.
"""

import os
import shutil
import socket
import tempfile
import threading
import time

import pytest

from src.constants import (
    SERVER_PORT,
    METHOD_ADD,
    METHOD_LOOKUP,
    METHOD_LIST,
)
from src.peer import UploadServer, download_rfc, find_local_rfcs
from src.protocol import format_p2s_request, parse_p2s_response
from src.socket_utils import recv_message_text
from src import server


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def temp_dir():
    """Create and cleanup temporary directory for test data."""
    tmpdir = tempfile.mkdtemp(prefix="p2pci_test_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def server_thread():
    """Start server in background."""
    server.peers.clear()
    server.index.clear()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def server_main_local():
        sock.bind(("0.0.0.0", SERVER_PORT))
        sock.listen()
        sock.settimeout(0.5)

        while getattr(server_thread, "running", True):
            try:
                conn, addr = sock.accept()
                t = threading.Thread(target=server._handle_peer, args=(conn, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception:
                break

    t = threading.Thread(target=server_main_local, daemon=True)
    t.start()
    server_thread.running = True
    time.sleep(0.1)

    yield

    server_thread.running = False
    try:
        sock.close()
    except Exception:
        pass
    time.sleep(0.1)


@pytest.fixture
def peer1_data(temp_dir):
    """Create test data for peer 1."""
    peer_dir = os.path.join(temp_dir, "peer1")
    os.makedirs(peer_dir, exist_ok=True)

    # Create test RFC files
    rfc_100 = os.path.join(peer_dir, "rfc100.txt")
    with open(rfc_100, "w") as f:
        f.write("RFC 100: Simple Explanation\n")
        f.write("This is test RFC 100 content.\n")
        f.write("Line 3\n")

    rfc_200 = os.path.join(peer_dir, "rfc200.txt")
    with open(rfc_200, "w") as f:
        f.write("RFC 200: Another Test\n")
        f.write("This is test RFC 200 content.\n")

    return peer_dir


@pytest.fixture
def peer2_data(temp_dir):
    """Create test data for peer 2."""
    peer_dir = os.path.join(temp_dir, "peer2")
    os.makedirs(peer_dir, exist_ok=True)

    # Start with empty directory, will download RFCs
    return peer_dir


# ============================================================================
# RFC DISCOVERY TESTS
# ============================================================================


@pytest.mark.integration
class TestRFCDiscovery:
    """Test RFC file discovery and metadata extraction."""

    def test_find_local_rfcs(self, peer1_data):
        """Find local RFC files and extract metadata."""
        rfcs = find_local_rfcs(peer1_data)

        assert len(rfcs) == 2
        assert rfcs[0][0] == 100  # RFC number
        assert "Simple Explanation" in rfcs[0][1]  # Title
        assert rfcs[0][2].endswith("rfc100.txt")  # Path

    def test_find_local_rfcs_empty_directory(self, peer2_data):
        """Find local RFCs in empty directory."""
        rfcs = find_local_rfcs(peer2_data)

        assert len(rfcs) == 0

    def test_find_local_rfcs_case_insensitive(self, temp_dir):
        """RFC file discovery is case-insensitive."""
        rfc_file = os.path.join(temp_dir, "RFC123.TXT")
        with open(rfc_file, "w") as f:
            f.write("RFC 123 Title\n")

        rfcs = find_local_rfcs(temp_dir)

        assert len(rfcs) == 1
        assert rfcs[0][0] == 123

    def test_find_local_rfcs_sorted_by_number(self, temp_dir):
        """RFCs are sorted by number."""
        for num in [300, 100, 200]:
            rfc_file = os.path.join(temp_dir, f"rfc{num}.txt")
            with open(rfc_file, "w") as f:
                f.write(f"RFC {num} Title\n")

        rfcs = find_local_rfcs(temp_dir)

        assert len(rfcs) == 3
        assert [r[0] for r in rfcs] == [100, 200, 300]


# ============================================================================
# UPLOAD SERVER TESTS
# ============================================================================


@pytest.mark.integration
class TestUploadServer:
    """Test peer upload server functionality."""

    def test_upload_server_starts_and_gets_port(self, peer1_data):
        """Upload server starts on ephemeral port."""
        upload = UploadServer(peer1_data)
        upload.start()

        assert upload.port > 0
        assert upload.port < 65536

        upload.stop()

    def test_upload_server_serves_rfc(self, peer1_data):
        """Upload server serves RFC files over P2P protocol."""
        upload = UploadServer(peer1_data)
        upload.start()

        try:
            # Connect and request RFC
            sock = socket.create_connection(("127.0.0.1", upload.port), timeout=2)
            req = (
                f"GET RFC 100 P2P-CI/1.0\r\n"
                f"Host: testhost\r\n"
                f"OS: TestOS\r\n"
                f"\r\n"
            )
            sock.sendall(req.encode("utf-8"))

            # Read response
            buf = b""
            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                buf += chunk

            sock.close()

            # Verify response
            assert b"200 OK" in buf
            assert b"Content-Length:" in buf
            assert b"Simple Explanation" in buf
        finally:
            upload.stop()

    def test_upload_server_returns_404_for_missing_rfc(self, peer1_data):
        """Upload server returns 404 for non-existent RFC."""
        upload = UploadServer(peer1_data)
        upload.start()

        try:
            sock = socket.create_connection(("127.0.0.1", upload.port), timeout=2)
            req = (
                f"GET RFC 999 P2P-CI/1.0\r\n"
                f"Host: testhost\r\n"
                f"OS: TestOS\r\n"
                f"\r\n"
            )
            sock.sendall(req.encode("utf-8"))

            buf = b""
            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                buf += chunk

            sock.close()

            assert b"404 Not Found" in buf
        finally:
            upload.stop()


# ============================================================================
# END-TO-END WORKFLOW TESTS
# ============================================================================


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete P2P-CI workflow."""

    def test_peer_register_and_lookup(self, server_thread, peer1_data):
        """Peer registers RFC and other peer looks it up."""
        # Peer 1: connect to server and register
        p1_sock = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)

        req = format_p2s_request(METHOD_ADD, 100, "127.0.0.1", 5000, "RFC 100: Simple Explanation")
        p1_sock.sendall(req.encode("utf-8"))
        resp = recv_message_text(p1_sock)
        status, records = parse_p2s_response(resp)
        assert status == 200

        # Peer 2: connect and lookup
        p2_sock = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)

        req = format_p2s_request(METHOD_LOOKUP, 100, "127.0.0.1", 5001, "")
        p2_sock.sendall(req.encode("utf-8"))
        resp = recv_message_text(p2_sock)
        status, records = parse_p2s_response(resp)

        assert status == 200
        assert len(records) == 1
        assert records[0][0] == 100
        assert records[0][2] == "127.0.0.1"
        assert records[0][3] == 5000

        p1_sock.close()
        p2_sock.close()

    def test_peer_list_query(self, server_thread, peer1_data):
        """Peer can query full RFC index."""
        # Peer 1: register two RFCs
        p1_sock = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)

        p1_sock.sendall(
            format_p2s_request(METHOD_ADD, 100, "127.0.0.1", 5000, "RFC 100").encode("utf-8")
        )
        recv_message_text(p1_sock)

        p1_sock.sendall(
            format_p2s_request(METHOD_ADD, 200, "127.0.0.1", 5000, "RFC 200").encode("utf-8")
        )
        recv_message_text(p1_sock)

        # Peer 2: LIST all
        p2_sock = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)

        p2_sock.sendall(format_p2s_request(METHOD_LIST, "ALL", "127.0.0.1", 5001, "").encode("utf-8"))
        resp = recv_message_text(p2_sock)
        status, records = parse_p2s_response(resp)

        assert status == 200
        assert len(records) == 2

        p1_sock.close()
        p2_sock.close()

    def test_download_rfc_between_peers(self, server_thread, peer1_data, peer2_data):
        """End-to-end: Peer 1 registers, Peer 2 downloads from Peer 1."""
        # Peer 1: start upload server
        upload = UploadServer(peer1_data)
        upload.start()

        try:
            # Peer 1: register RFC with server
            p1_sock = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)
            p1_sock.sendall(
                format_p2s_request(METHOD_ADD, 100, "127.0.0.1", upload.port, "RFC 100").encode("utf-8")
            )
            recv_message_text(p1_sock)
            time.sleep(0.1)  # Ensure server processes ADD

            # Peer 2: lookup RFC
            p2_sock = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)
            p2_sock.sendall(format_p2s_request(METHOD_LOOKUP, 100, "127.0.0.1", 5001, "").encode("utf-8"))
            resp = recv_message_text(p2_sock)
            status, records = parse_p2s_response(resp)

            assert status == 200
            assert len(records) == 1
            host, port = records[0][2], records[0][3]

            # Peer 2: download RFC from Peer 1
            download_path = os.path.join(peer2_data, "rfc100.txt")
            success, data = download_rfc(host, port, 100, download_path)

            assert success
            assert os.path.exists(download_path)

            # Verify downloaded content
            with open(download_path, "rb") as f:
                content = f.read()
            assert b"RFC 100: Simple Explanation" in content
            assert b"This is test RFC 100 content" in content

            p1_sock.close()
            p2_sock.close()
        finally:
            upload.stop()

    def test_multiple_peers_share_rfcs(self, server_thread, temp_dir):
        """Multiple peers register and query index."""
        # Peer 1: register one RFC
        p1_sock = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)
        p1_sock.sendall(
            format_p2s_request(METHOD_ADD, 100, "127.0.0.1", 5000, "RFC 100").encode("utf-8")
        )
        recv_message_text(p1_sock)
        time.sleep(0.1)

        # Peer 2: register one RFC
        p2_sock = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)
        p2_sock.sendall(
            format_p2s_request(METHOD_ADD, 200, "127.0.0.1", 5001, "RFC 200").encode("utf-8")
        )
        recv_message_text(p2_sock)
        time.sleep(0.1)

        # Peer 3: list all
        p3_sock = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)
        p3_sock.sendall(format_p2s_request(METHOD_LIST, "ALL", "127.0.0.1", 5002, "").encode("utf-8"))
        resp = recv_message_text(p3_sock)
        status, records = parse_p2s_response(resp)

        assert status == 200
        assert len(records) == 2
        rfc_numbers = [r[0] for r in records]
        assert set(rfc_numbers) == {100, 200}

        p1_sock.close()
        p2_sock.close()
        p3_sock.close()

    def test_peer_disconnect_cleanup(self, server_thread):
        """When peer disconnects, its RFCs are removed from index."""
        # Peer 1: register RFC
        p1_sock = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)
        p1_sock.sendall(
            format_p2s_request(METHOD_ADD, 100, "127.0.0.1", 5000, "RFC 100").encode("utf-8")
        )
        recv_message_text(p1_sock)

        # Peer 2: verify it's there
        p2_sock = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)
        p2_sock.sendall(format_p2s_request(METHOD_LOOKUP, 100, "127.0.0.1", 5001, "").encode("utf-8"))
        resp = recv_message_text(p2_sock)
        status, records = parse_p2s_response(resp)
        assert status == 200
        assert len(records) == 1

        # Peer 1: disconnect
        p1_sock.close()
        time.sleep(0.2)

        # Peer 2: should not find it anymore
        p2_sock.sendall(format_p2s_request(METHOD_LOOKUP, 100, "127.0.0.1", 5001, "").encode("utf-8"))
        resp = recv_message_text(p2_sock)
        status, records = parse_p2s_response(resp)

        assert status == 404
        assert len(records) == 0

        p2_sock.close()
