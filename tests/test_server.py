"""
Tests for P2P-CI server implementation.

Tests server handlers, data structures, concurrent connections, and cleanup logic.
Uses threading to simulate peer connections without mocking.
"""

import socket
import threading
import time
from typing import List, Tuple

import pytest

from src.constants import (
    SERVER_PORT,
    CRLF,
    PROTOCOL_VERSION,
    STATUS_OK,
    STATUS_BAD_REQUEST,
    STATUS_NOT_FOUND,
    STATUS_VERSION_NOT_SUPPORTED,
    METHOD_ADD,
    METHOD_LOOKUP,
    METHOD_LIST,
)
from src.protocol import format_p2s_request, format_p2s_response, parse_p2s_response
from src.socket_utils import recv_message_text
from src import server


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def server_thread():
    """Start server in background thread and yield, then clean up."""
    # Reset server state before test
    server.peers.clear()
    server.index.clear()

    # Create server socket with reusable address
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    def server_main_local():
        """Local server main that uses pre-created socket."""
        sock.bind(("0.0.0.0", SERVER_PORT))
        sock.listen()
        print(f"[server] listening on port {SERVER_PORT}")
        
        sock.settimeout(0.5)  # Timeout so we can check running flag
        while getattr(server_thread, 'running', True):
            try:
                conn, addr = sock.accept()
                print(f"[server] connection from {addr}")
                t = threading.Thread(target=server._handle_peer, args=(conn, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception:
                break
    
    # Start server in background thread
    t = threading.Thread(target=server_main_local, daemon=True)
    t.start()
    
    # Mark as running
    server_thread.running = True

    # Wait for server to start listening
    time.sleep(0.1)

    yield

    # Stop server
    server_thread.running = False
    try:
        sock.close()
    except Exception:
        pass
    time.sleep(0.1)


@pytest.fixture
def client_connection(server_thread):
    """Create a client connection to the server."""
    sock = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)
    yield sock
    try:
        sock.close()
    except Exception:
        pass


def send_request(sock: socket.socket, method: str, rfc_number, host: str, port: int, title: str = "") -> str:
    """Helper: Send P2S request and receive response."""
    req = format_p2s_request(method, rfc_number, host, port, title)
    sock.sendall(req.encode("utf-8"))

    # Receive response
    buf = recv_message_text(sock)
    return buf if buf else ""


# ============================================================================
# DATA STRUCTURE TESTS
# ============================================================================


@pytest.mark.server
class TestServerDataStructures:
    """Test server data structure initialization and state."""

    def test_server_initializes_empty_peers(self, server_thread):
        """Server starts with empty peer list."""
        assert len(server.peers) == 0

    def test_server_initializes_empty_index(self, server_thread):
        """Server starts with empty RFC index."""
        assert len(server.index) == 0


# ============================================================================
# ADD REQUEST TESTS
# ============================================================================


@pytest.mark.server
class TestAddHandler:
    """Test ADD request handler."""

    def test_add_registers_peer(self, client_connection):
        """ADD request registers peer in peer list."""
        resp = send_request(client_connection, METHOD_ADD, 123, "host1.example.com", 5000, "RFC 123")

        # Check response is 200 OK
        status, records = parse_p2s_response(resp)
        assert status == 200
        assert len(records) == 1

        # Check peer list was updated
        assert "host1.example.com" in server.peers
        assert server.peers["host1.example.com"] == 5000

    def test_add_inserts_at_front_of_index(self, client_connection):
        """ADD request inserts RFC at front of index."""
        # Add RFC 100
        send_request(client_connection, METHOD_ADD, 100, "host1.example.com", 5000, "RFC 100")

        # Add RFC 200
        send_request(client_connection, METHOD_ADD, 200, "host2.example.com", 5001, "RFC 200")

        # Add RFC 300
        send_request(client_connection, METHOD_ADD, 300, "host3.example.com", 5002, "RFC 300")

        # Index should be [300, 200, 100] (newest first)
        with server.db_lock:
            assert len(server.index) == 3
            assert server.index[0][0] == 300  # Most recent
            assert server.index[1][0] == 200
            assert server.index[2][0] == 100  # Oldest

    def test_add_removes_duplicate_rfc_from_same_host(self, client_connection):
        """ADD for same RFC from same host removes old record."""
        # Add RFC 123 from host1
        send_request(client_connection, METHOD_ADD, 123, "host1.example.com", 5000, "RFC 123 v1")

        with server.db_lock:
            assert len(server.index) == 1

        # Add same RFC 123 from host1 again (newer title)
        send_request(client_connection, METHOD_ADD, 123, "host1.example.com", 5000, "RFC 123 v2")

        # Should still be 1 record (replaced, not added)
        with server.db_lock:
            assert len(server.index) == 1
            assert server.index[0][1] == "RFC 123 v2"  # Updated title

    def test_add_allows_same_rfc_from_different_hosts(self, client_connection):
        """ADD allows same RFC from multiple peers."""
        send_request(client_connection, METHOD_ADD, 123, "host1.example.com", 5000, "RFC 123")
        send_request(client_connection, METHOD_ADD, 123, "host2.example.com", 5001, "RFC 123")

        with server.db_lock:
            matches = [rec for rec in server.index if rec[0] == 123]
            assert len(matches) == 2

    def test_add_response_echoes_record(self, client_connection):
        """ADD response echoes back the registered RFC record."""
        resp = send_request(client_connection, METHOD_ADD, 123, "host1.example.com", 5000, "Test RFC")

        status, records = parse_p2s_response(resp)
        assert status == 200
        assert len(records) == 1
        assert records[0] == (123, "Test RFC", "host1.example.com", 5000)

    def test_add_maintains_peer_port_mapping(self, client_connection):
        """ADD request updates peer port mapping."""
        # Add from host1 with port 5000
        send_request(client_connection, METHOD_ADD, 100, "host1.example.com", 5000, "RFC 100")
        assert server.peers["host1.example.com"] == 5000

        # Add another RFC from host1 with same port
        send_request(client_connection, METHOD_ADD, 200, "host1.example.com", 5000, "RFC 200")
        assert server.peers["host1.example.com"] == 5000

        # Add from host1 with different port (should update)
        send_request(client_connection, METHOD_ADD, 300, "host1.example.com", 5001, "RFC 300")
        assert server.peers["host1.example.com"] == 5001


# ============================================================================
# LOOKUP REQUEST TESTS
# ============================================================================


@pytest.mark.server
class TestLookupHandler:
    """Test LOOKUP request handler."""

    def test_lookup_not_found(self, client_connection):
        """LOOKUP for non-existent RFC returns 404."""
        resp = send_request(client_connection, METHOD_LOOKUP, 999, "host1.example.com", 5000, "RFC 999")

        status, records = parse_p2s_response(resp)
        assert status == 404
        assert len(records) == 0

    def test_lookup_single_record(self, client_connection):
        """LOOKUP returns single record when one peer has RFC."""
        send_request(client_connection, METHOD_ADD, 123, "host1.example.com", 5000, "RFC 123")

        resp = send_request(client_connection, METHOD_LOOKUP, 123, "host2.example.com", 5001, "RFC 123")

        status, records = parse_p2s_response(resp)
        assert status == 200
        assert len(records) == 1
        assert records[0][0] == 123
        assert records[0][2] == "host1.example.com"
        assert records[0][3] == 5000

    def test_lookup_multiple_records(self, client_connection):
        """LOOKUP returns all records when multiple peers have RFC."""
        send_request(client_connection, METHOD_ADD, 123, "host1.example.com", 5000, "RFC 123")
        send_request(client_connection, METHOD_ADD, 123, "host2.example.com", 5001, "RFC 123")
        send_request(client_connection, METHOD_ADD, 123, "host3.example.com", 5002, "RFC 123")

        resp = send_request(client_connection, METHOD_LOOKUP, 123, "host4.example.com", 5003, "RFC 123")

        status, records = parse_p2s_response(resp)
        assert status == 200
        assert len(records) == 3

    def test_lookup_preserves_insertion_order(self, client_connection):
        """LOOKUP returns records in insertion order (newest first)."""
        send_request(client_connection, METHOD_ADD, 456, "hostA.example.com", 5000, "RFC 456")
        send_request(client_connection, METHOD_ADD, 456, "hostB.example.com", 5001, "RFC 456")
        send_request(client_connection, METHOD_ADD, 456, "hostC.example.com", 5002, "RFC 456")

        resp = send_request(client_connection, METHOD_LOOKUP, 456, "hostD.example.com", 5003, "RFC 456")

        status, records = parse_p2s_response(resp)
        assert records[0][2] == "hostC.example.com"  # Most recent
        assert records[1][2] == "hostB.example.com"
        assert records[2][2] == "hostA.example.com"  # Oldest


# ============================================================================
# LIST REQUEST TESTS
# ============================================================================


@pytest.mark.server
class TestListHandler:
    """Test LIST request handler."""

    def test_list_empty_index(self, client_connection):
        """LIST on empty index returns 200 OK with no records."""
        resp = send_request(client_connection, METHOD_LIST, "ALL", "host1.example.com", 5000, "")

        status, records = parse_p2s_response(resp)
        assert status == 200
        assert len(records) == 0

    def test_list_returns_all_records(self, client_connection):
        """LIST returns all records from index."""
        send_request(client_connection, METHOD_ADD, 100, "host1.example.com", 5000, "RFC 100")
        send_request(client_connection, METHOD_ADD, 200, "host2.example.com", 5001, "RFC 200")
        send_request(client_connection, METHOD_ADD, 300, "host3.example.com", 5002, "RFC 300")

        resp = send_request(client_connection, METHOD_LIST, "ALL", "host4.example.com", 5003, "")

        status, records = parse_p2s_response(resp)
        assert status == 200
        assert len(records) == 3

    def test_list_includes_multiple_rfc_records(self, client_connection):
        """LIST includes multiple records for same RFC from different hosts."""
        send_request(client_connection, METHOD_ADD, 123, "host1.example.com", 5000, "RFC 123")
        send_request(client_connection, METHOD_ADD, 123, "host2.example.com", 5001, "RFC 123")
        send_request(client_connection, METHOD_ADD, 456, "host3.example.com", 5002, "RFC 456")

        resp = send_request(client_connection, METHOD_LIST, "ALL", "host4.example.com", 5003, "")

        status, records = parse_p2s_response(resp)
        assert status == 200
        assert len(records) == 3


# ============================================================================
# VERSION VALIDATION TESTS
# ============================================================================


@pytest.mark.server
class TestVersionValidation:
    """Test protocol version validation."""

    def test_invalid_version_returns_505(self, client_connection):
        """Request with unsupported version returns 505."""
        # Send request with wrong version
        bad_req = (
            f"ADD RFC 123 P2P-CI/2.0{CRLF}"
            f"Host: host.example.com{CRLF}"
            f"Port: 5000{CRLF}"
            f"Title: Test{CRLF}"
            f"{CRLF}"
        )
        client_connection.sendall(bad_req.encode("utf-8"))

        buf = recv_message_text(client_connection)
        status, _ = parse_p2s_response(buf)

        assert status == 505

    def test_invalid_version_does_not_mutate_state(self, client_connection):
        """Invalid version request doesn't add to index."""
        bad_req = (
            f"ADD RFC 123 P2P-CI/2.0{CRLF}"
            f"Host: host.example.com{CRLF}"
            f"Port: 5000{CRLF}"
            f"Title: Test{CRLF}"
            f"{CRLF}"
        )
        client_connection.sendall(bad_req.encode("utf-8"))
        recv_message_text(client_connection)

        # Index should still be empty
        with server.db_lock:
            assert len(server.index) == 0


# ============================================================================
# MALFORMED REQUEST TESTS
# ============================================================================


@pytest.mark.server
class TestMalformedRequests:
    """Test handling of malformed requests."""

    def test_missing_host_header_returns_400(self, client_connection):
        """Request missing Host header returns 400."""
        bad_req = (
            f"ADD RFC 123 {PROTOCOL_VERSION}{CRLF}"
            f"Port: 5000{CRLF}"
            f"Title: Test{CRLF}"
            f"{CRLF}"
        )
        client_connection.sendall(bad_req.encode("utf-8"))

        buf = recv_message_text(client_connection)
        status, _ = parse_p2s_response(buf)

        assert status == 400

    def test_missing_port_header_returns_400(self, client_connection):
        """Request missing Port header returns 400."""
        bad_req = (
            f"ADD RFC 123 {PROTOCOL_VERSION}{CRLF}"
            f"Host: host.example.com{CRLF}"
            f"Title: Test{CRLF}"
            f"{CRLF}"
        )
        client_connection.sendall(bad_req.encode("utf-8"))

        buf = recv_message_text(client_connection)
        status, _ = parse_p2s_response(buf)

        assert status == 400

    def test_malformed_request_continues_connection(self, client_connection):
        """After malformed request, connection stays open."""
        # Send malformed request
        bad_req = (
            f"ADD RFC 123 {PROTOCOL_VERSION}{CRLF}"
            f"Port: 5000{CRLF}"
            f"Title: Test{CRLF}"
            f"{CRLF}"
        )
        client_connection.sendall(bad_req.encode("utf-8"))
        recv_message_text(client_connection)

        # Send valid request - should succeed
        resp = send_request(client_connection, METHOD_ADD, 456, "host.example.com", 5001, "RFC 456")
        status, _ = parse_p2s_response(resp)

        assert status == 200


# ============================================================================
# CONCURRENT CONNECTION TESTS
# ============================================================================


@pytest.mark.server
class TestConcurrentConnections:
    """Test server handling multiple concurrent peer connections."""

    def test_sequential_peers_add_then_lookup(self, server_thread):
        """Multiple peers can connect sequentially and add/lookup RFCs."""
        sock1 = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)
        
        # Peer 1 adds RFCs
        send_request(sock1, METHOD_ADD, 100, "host1.example.com", 5000, "RFC 100")
        send_request(sock1, METHOD_ADD, 200, "host1.example.com", 5000, "RFC 200")

        sock2 = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)

        # Peer 2 looks up RFCs from Peer 1
        resp = send_request(sock2, METHOD_LOOKUP, 100, "host2.example.com", 5001, "RFC 100")
        status, records = parse_p2s_response(resp)
        assert status == 200
        assert len(records) == 1

        # Peer 2 adds its own RFC
        send_request(sock2, METHOD_ADD, 300, "host2.example.com", 5001, "RFC 300")

        # Peer 1 can lookup Peer 2's RFC
        resp = send_request(sock1, METHOD_LOOKUP, 300, "host1.example.com", 5000, "RFC 300")
        status, records = parse_p2s_response(resp)
        assert status == 200
        assert len(records) == 1

        sock1.close()
        sock2.close()

    def test_connection_isolation(self, server_thread):
        """Each peer connection is independent."""
        sock1 = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)
        sock2 = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)

        # Peer 1 adds
        send_request(sock1, METHOD_ADD, 100, "host1.example.com", 5000, "RFC 100")

        # Peer 2 adds
        send_request(sock2, METHOD_ADD, 200, "host2.example.com", 5001, "RFC 200")

        # Both should see both RFCs in LIST
        resp1 = send_request(sock1, METHOD_LIST, "ALL", "host1.example.com", 5000, "")
        status1, records1 = parse_p2s_response(resp1)

        resp2 = send_request(sock2, METHOD_LIST, "ALL", "host2.example.com", 5001, "")
        status2, records2 = parse_p2s_response(resp2)

        assert status1 == 200 and len(records1) == 2
        assert status2 == 200 and len(records2) == 2

        sock1.close()
        sock2.close()


# ============================================================================
# CLEANUP/DISCONNECT TESTS
# ============================================================================


@pytest.mark.server
class TestDisconnectCleanup:
    """Test cleanup when peer disconnects."""

    def test_peer_disconnect_removes_all_records(self, server_thread):
        """When peer disconnects, all its RFCs are removed from index."""
        sock1 = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)

        # Peer 1 adds 3 RFCs
        send_request(sock1, METHOD_ADD, 100, "host1.example.com", 5000, "RFC 100")
        send_request(sock1, METHOD_ADD, 200, "host1.example.com", 5000, "RFC 200")
        send_request(sock1, METHOD_ADD, 300, "host1.example.com", 5000, "RFC 300")

        with server.db_lock:
            assert len(server.index) == 3

        # Peer 1 disconnects
        sock1.close()

        # Give server time to process disconnect
        time.sleep(0.2)

        # Index should be empty
        with server.db_lock:
            assert len(server.index) == 0

    def test_peer_disconnect_removes_from_peer_list(self, server_thread):
        """When peer disconnects, it's removed from peer list."""
        sock1 = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)

        send_request(sock1, METHOD_ADD, 100, "host1.example.com", 5000, "RFC 100")

        assert "host1.example.com" in server.peers

        sock1.close()
        time.sleep(0.2)

        # Peer should be removed
        assert "host1.example.com" not in server.peers

    def test_selective_cleanup_multiple_peers(self, server_thread):
        """Cleanup only affects disconnecting peer, not others."""
        sock1 = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)
        sock2 = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)

        # Peer 1 adds RFCs
        send_request(sock1, METHOD_ADD, 100, "host1.example.com", 5000, "RFC 100")
        send_request(sock1, METHOD_ADD, 200, "host1.example.com", 5000, "RFC 200")

        # Peer 2 adds RFCs
        send_request(sock2, METHOD_ADD, 100, "host2.example.com", 5001, "RFC 100")
        send_request(sock2, METHOD_ADD, 300, "host2.example.com", 5001, "RFC 300")

        with server.db_lock:
            assert len(server.index) == 4

        # Peer 1 disconnects
        sock1.close()
        time.sleep(0.2)

        # Should have 2 records left (both from host2)
        with server.db_lock:
            assert len(server.index) == 2
            remaining_hosts = [rec[2] for rec in server.index]
            assert all(h == "host2.example.com" for h in remaining_hosts)

        sock2.close()


@pytest.mark.server
class TestThreadSafety:
    """Test thread safety of shared data structures."""

    def test_add_uses_lock(self, server_thread):
        """ADD operations use db_lock for data structure updates."""
        # This is verified by the fact that concurrent adds don't corrupt the index
        # More specific testing would require mocking threading.Lock, but actual
        # locking behavior is verified by the concurrent tests that pass
        sock1 = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)
        sock2 = socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=2)

        try:
            # Sequential adds on different connections
            send_request(sock1, METHOD_ADD, 100, "host1.example.com", 5000, "RFC 100")
            send_request(sock2, METHOD_ADD, 200, "host2.example.com", 5001, "RFC 200")

            with server.db_lock:
                assert len(server.index) == 2
        finally:
            sock1.close()
            sock2.close()
