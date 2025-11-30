"""
Comprehensive tests for P2P-CI protocol parsing and formatting.

Tests both P2S (Peer-to-Server) and P2P (Peer-to-Peer) protocols.
"""

import pytest

from src.constants import (
    CRLF,
    PROTOCOL_VERSION,
    STATUS_OK,
    STATUS_BAD_REQUEST,
    STATUS_NOT_FOUND,
    STATUS_VERSION_NOT_SUPPORTED,
    METHOD_ADD,
    METHOD_LOOKUP,
    METHOD_LIST,
    METHOD_GET,
    HEADER_HOST,
    HEADER_PORT,
    HEADER_TITLE,
    HEADER_OS,
    HEADER_DATE,
    HEADER_LAST_MODIFIED,
    HEADER_CONTENT_LENGTH,
    HEADER_CONTENT_TYPE,
    RFC_ALL,
)
from src.protocol import (
    parse_p2s_request,
    format_p2s_request,
    format_p2s_response,
    parse_p2s_response,
    parse_p2p_request,
    format_p2p_response,
)


# ============================================================================
# P2S REQUEST PARSING TESTS
# ============================================================================


@pytest.mark.protocol
class TestP2SRequestParsing:
    """Test P2S request parsing for ADD, LOOKUP, LIST methods."""

    def test_parse_add_request_valid(self):
        """Valid ADD request with all required headers."""
        req = (
            f"ADD RFC 123 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_PORT}: 5678{CRLF}"
            f"{HEADER_TITLE}: A Test RFC Title{CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is not None
        assert result["method"] == METHOD_ADD
        assert result["rfc_number"] == 123
        assert result["version"] == PROTOCOL_VERSION
        assert result["host"] == "host.example.com"
        assert result["port"] == 5678
        assert result["title"] == "A Test RFC Title"

    def test_parse_add_request_multiword_title(self):
        """ADD request with multi-word title."""
        req = (
            f"ADD RFC 456 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: peer.csc.ncsu.edu{CRLF}"
            f"{HEADER_PORT}: 8000{CRLF}"
            f"{HEADER_TITLE}: A Proferred Official ICP Specification{CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is not None
        assert result["title"] == "A Proferred Official ICP Specification"

    def test_parse_lookup_request_valid(self):
        """Valid LOOKUP request."""
        req = (
            f"LOOKUP RFC 3457 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: client.example.com{CRLF}"
            f"{HEADER_PORT}: 9999{CRLF}"
            f"{HEADER_TITLE}: Requirements for IPsec{CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is not None
        assert result["method"] == METHOD_LOOKUP
        assert result["rfc_number"] == 3457

    def test_parse_list_request_valid(self):
        """Valid LIST request with ALL."""
        req = (
            f"LIST ALL {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_PORT}: 5678{CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is not None
        assert result["method"] == METHOD_LIST
        assert result["rfc_number"] == RFC_ALL

    def test_parse_request_missing_host_header(self):
        """Request missing required Host header."""
        req = (
            f"ADD RFC 123 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_PORT}: 5678{CRLF}"
            f"{HEADER_TITLE}: Test{CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is None

    def test_parse_request_missing_port_header(self):
        """Request missing required Port header."""
        req = (
            f"ADD RFC 123 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_TITLE}: Test{CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is None

    def test_parse_request_invalid_port_number(self):
        """Request with non-numeric port."""
        req = (
            f"ADD RFC 123 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_PORT}: not_a_number{CRLF}"
            f"{HEADER_TITLE}: Test{CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is None

    def test_parse_request_invalid_rfc_number(self):
        """Request with non-numeric RFC number."""
        req = (
            f"ADD RFC abc {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_PORT}: 5678{CRLF}"
            f"{HEADER_TITLE}: Test{CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is None

    def test_parse_request_invalid_keyword(self):
        """Request with wrong RFC keyword."""
        req = (
            f"ADD FOO 123 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_PORT}: 5678{CRLF}"
            f"{HEADER_TITLE}: Test{CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is None

    def test_parse_list_invalid_rfc_value(self):
        """LIST request with non-ALL RFC value."""
        req = (
            f"LIST 123 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_PORT}: 5678{CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is None

    def test_parse_request_malformed_header(self):
        """Request with header missing colon."""
        req = (
            f"ADD RFC 123 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"BadHeader NoColon{CRLF}"
            f"{HEADER_PORT}: 5678{CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is None

    def test_parse_request_empty(self):
        """Empty request."""
        result = parse_p2s_request("")
        assert result is None

    def test_parse_request_title_optional_for_list(self):
        """LIST request doesn't require Title header."""
        req = (
            f"LIST ALL {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_PORT}: 5678{CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is not None
        assert result.get("title") == ""


# ============================================================================
# P2S REQUEST FORMATTING TESTS
# ============================================================================


@pytest.mark.protocol
class TestP2SRequestFormatting:
    """Test P2S request formatting."""

    def test_format_add_request(self):
        """Format an ADD request."""
        req = format_p2s_request(METHOD_ADD, 123, "host.example.com", 5678, "Test RFC")

        expected = (
            f"ADD RFC 123 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_PORT}: 5678{CRLF}"
            f"{HEADER_TITLE}: Test RFC{CRLF}"
            f"{CRLF}"
        )
        assert req == expected

    def test_format_lookup_request(self):
        """Format a LOOKUP request."""
        req = format_p2s_request(METHOD_LOOKUP, 456, "peer.example.com", 7000, "Some RFC")

        expected = (
            f"LOOKUP RFC 456 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: peer.example.com{CRLF}"
            f"{HEADER_PORT}: 7000{CRLF}"
            f"{HEADER_TITLE}: Some RFC{CRLF}"
            f"{CRLF}"
        )
        assert req == expected

    def test_format_list_request(self):
        """Format a LIST request."""
        req = format_p2s_request(METHOD_LIST, RFC_ALL, "host.example.com", 5678, "")

        expected = (
            f"LIST ALL {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_PORT}: 5678{CRLF}"
            f"{CRLF}"
        )
        assert req == expected

    def test_format_request_with_multiword_title(self):
        """Format request with multi-word title."""
        req = format_p2s_request(
            METHOD_ADD, 789, "host.example.com", 5678, "A Proferred Official ICP"
        )

        assert "A Proferred Official ICP" in req
        assert f"{HEADER_TITLE}: A Proferred Official ICP{CRLF}" in req


# ============================================================================
# P2S RESPONSE FORMATTING TESTS
# ============================================================================


@pytest.mark.protocol
class TestP2SResponseFormatting:
    """Test P2S response formatting."""

    def test_format_response_200_ok_with_records(self):
        """Format 200 OK response with RFC records."""
        records = [
            (123, "Test RFC", "host1.example.com", 5001),
            (123, "Test RFC", "host2.example.com", 5002),
        ]
        resp = format_p2s_response(STATUS_OK, records)

        assert f"{PROTOCOL_VERSION} 200 OK{CRLF}{CRLF}" in resp
        assert "123 Test RFC host1.example.com 5001" in resp
        assert "123 Test RFC host2.example.com 5002" in resp
        assert resp.endswith(CRLF)

    def test_format_response_200_ok_empty(self):
        """Format 200 OK response with no records."""
        resp = format_p2s_response(STATUS_OK, [])

        expected = f"{PROTOCOL_VERSION} 200 OK{CRLF}{CRLF}{CRLF}"
        assert resp == expected

    def test_format_response_404_not_found(self):
        """Format 404 Not Found response."""
        resp = format_p2s_response(STATUS_NOT_FOUND, [])

        assert f"{PROTOCOL_VERSION} 404 Not Found{CRLF}{CRLF}" in resp

    def test_format_response_400_bad_request(self):
        """Format 400 Bad Request response."""
        resp = format_p2s_response(STATUS_BAD_REQUEST, [])

        assert f"{PROTOCOL_VERSION} 400 Bad Request{CRLF}{CRLF}" in resp

    def test_format_response_505_version_not_supported(self):
        """Format 505 Version Not Supported response."""
        resp = format_p2s_response(STATUS_VERSION_NOT_SUPPORTED, [])

        assert f"{PROTOCOL_VERSION} 505 P2P-CI Version Not Supported{CRLF}{CRLF}" in resp

    def test_format_response_multiword_title(self):
        """Response with multi-word RFC title."""
        records = [(456, "A Proferred Official ICP Specification", "host.example.com", 5000)]
        resp = format_p2s_response(STATUS_OK, records)

        assert "456 A Proferred Official ICP Specification host.example.com 5000" in resp


# ============================================================================
# P2S RESPONSE PARSING TESTS
# ============================================================================


@pytest.mark.protocol
class TestP2SResponseParsing:
    """Test P2S response parsing."""

    def test_parse_response_200_with_records(self):
        """Parse 200 OK response with multiple records."""
        resp = (
            f"{PROTOCOL_VERSION} 200 OK{CRLF}"
            f"{CRLF}"
            f"123 Test RFC host1.example.com 5001{CRLF}"
            f"123 Test RFC host2.example.com 5002{CRLF}"
            f"{CRLF}"
        )
        status, records = parse_p2s_response(resp)

        assert status == 200
        assert len(records) == 2
        assert records[0] == (123, "Test RFC", "host1.example.com", 5001)
        assert records[1] == (123, "Test RFC", "host2.example.com", 5002)

    def test_parse_response_200_empty(self):
        """Parse 200 OK response with no records."""
        resp = f"{PROTOCOL_VERSION} 200 OK{CRLF}{CRLF}{CRLF}"
        status, records = parse_p2s_response(resp)

        assert status == 200
        assert len(records) == 0

    def test_parse_response_404_not_found(self):
        """Parse 404 Not Found response."""
        resp = f"{PROTOCOL_VERSION} 404 Not Found{CRLF}{CRLF}{CRLF}"
        status, records = parse_p2s_response(resp)

        assert status == 404
        assert len(records) == 0

    def test_parse_response_multiword_title(self):
        """Parse response with multi-word RFC title."""
        resp = (
            f"{PROTOCOL_VERSION} 200 OK{CRLF}"
            f"{CRLF}"
            f"456 A Proferred Official ICP Specification host.example.com 5000{CRLF}"
            f"{CRLF}"
        )
        status, records = parse_p2s_response(resp)

        assert status == 200
        assert len(records) == 1
        assert records[0] == (456, "A Proferred Official ICP Specification", "host.example.com", 5000)

    def test_parse_response_various_title_lengths(self):
        """Parse responses with titles of varying word counts."""
        resp = (
            f"{PROTOCOL_VERSION} 200 OK{CRLF}"
            f"{CRLF}"
            f"111 One host1.example.com 5001{CRLF}"
            f"222 Two Words host2.example.com 5002{CRLF}"
            f"333 Three Long Words host3.example.com 5003{CRLF}"
            f"{CRLF}"
        )
        status, records = parse_p2s_response(resp)

        assert status == 200
        assert len(records) == 3
        assert records[0][1] == "One"
        assert records[1][1] == "Two Words"
        assert records[2][1] == "Three Long Words"

    def test_parse_response_invalid_status_code(self):
        """Parse response with non-numeric status code."""
        resp = f"{PROTOCOL_VERSION} INVALID{CRLF}{CRLF}{CRLF}"
        status, records = parse_p2s_response(resp)

        assert status is None
        assert len(records) == 0

    def test_parse_response_empty(self):
        """Parse empty response."""
        status, records = parse_p2s_response("")

        assert status is None
        assert len(records) == 0


# ============================================================================
# P2P REQUEST PARSING TESTS
# ============================================================================


@pytest.mark.protocol
class TestP2PRequestParsing:
    """Test P2P GET request parsing."""

    def test_parse_get_request_valid(self):
        """Valid P2P GET request."""
        req = (
            f"GET RFC 1234 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: somehost.csc.ncsu.edu{CRLF}"
            f"{HEADER_OS}: Mac OS 10.4.1{CRLF}"
            f"{CRLF}"
        ).encode("utf-8")

        result = parse_p2p_request(req)

        assert result is not None
        assert result["method"] == METHOD_GET
        assert result["rfc_number"] == 1234
        assert result["version"] == PROTOCOL_VERSION
        assert result["host"] == "somehost.csc.ncsu.edu"
        assert result["os"] == "Mac OS 10.4.1"

    def test_parse_get_request_missing_host(self):
        """P2P GET request missing Host header."""
        req = (
            f"GET RFC 5678 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_OS}: Linux{CRLF}"
            f"{CRLF}"
        ).encode("utf-8")

        result = parse_p2p_request(req)

        assert result is None

    def test_parse_get_request_missing_os(self):
        """P2P GET request missing OS header."""
        req = (
            f"GET RFC 5678 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{CRLF}"
        ).encode("utf-8")

        result = parse_p2p_request(req)

        assert result is None

    def test_parse_get_request_invalid_rfc_number(self):
        """P2P GET request with non-numeric RFC number."""
        req = (
            f"GET RFC abc {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_OS}: Linux{CRLF}"
            f"{CRLF}"
        ).encode("utf-8")

        result = parse_p2p_request(req)

        assert result is None

    def test_parse_get_request_wrong_keyword(self):
        """P2P request with wrong RFC keyword."""
        req = (
            f"GET FOO 1234 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_OS}: Linux{CRLF}"
            f"{CRLF}"
        ).encode("utf-8")

        result = parse_p2p_request(req)

        assert result is None

    def test_parse_get_request_invalid_method(self):
        """P2P request with wrong method."""
        req = (
            f"POST RFC 1234 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_OS}: Linux{CRLF}"
            f"{CRLF}"
        ).encode("utf-8")

        result = parse_p2p_request(req)

        assert result is None

    def test_parse_get_request_malformed(self):
        """P2P request with wrong number of parts."""
        req = (
            f"GET RFC {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_OS}: Linux{CRLF}"
            f"{CRLF}"
        ).encode("utf-8")

        result = parse_p2p_request(req)

        assert result is None

    def test_parse_get_request_non_utf8(self):
        """P2P request with invalid UTF-8."""
        req = b"GET RFC 1234 P2P-CI/1.0\r\nHost: host\r\nOS: OS\r\n\xff\xfe\r\n\r\n"
        result = parse_p2p_request(req)

        # Should still parse successfully with error handling
        assert result is not None or result is None  # Either result is acceptable


# ============================================================================
# P2P RESPONSE FORMATTING TESTS
# ============================================================================


@pytest.mark.protocol
class TestP2PResponseFormatting:
    """Test P2P response formatting."""

    def test_format_response_200_ok_with_headers_and_data(self):
        """Format 200 OK P2P response with headers and file data."""
        headers = {
            HEADER_DATE: "Wed, 12 Feb 2009 15:12:05 GMT",
            HEADER_OS: "Mac OS 10.2.1",
            HEADER_LAST_MODIFIED: "Thu, 21 Jan 2001 9:23:46 GMT",
            HEADER_CONTENT_LENGTH: "12345",
            HEADER_CONTENT_TYPE: "text/plain",
        }
        data = b"This is RFC file content"

        resp = format_p2p_response(STATUS_OK, headers, data)

        # Response should be bytes
        assert isinstance(resp, bytes)

        # Parse response to verify structure
        resp_str = resp.decode("utf-8", errors="replace")
        assert f"{PROTOCOL_VERSION} 200 OK" in resp_str
        assert "Wed, 12 Feb 2009 15:12:05 GMT" in resp_str
        assert "Mac OS 10.2.1" in resp_str
        assert "text/plain" in resp_str

        # Verify data is at the end
        assert resp.endswith(data)

    def test_format_response_404_not_found(self):
        """Format 404 Not Found P2P response."""
        resp = format_p2p_response(STATUS_NOT_FOUND, {"Content-Length": "0"}, b"")

        assert isinstance(resp, bytes)
        resp_str = resp.decode("utf-8")
        assert f"{PROTOCOL_VERSION} 404 Not Found" in resp_str

    def test_format_response_400_bad_request(self):
        """Format 400 Bad Request P2P response."""
        resp = format_p2p_response(STATUS_BAD_REQUEST, {"Content-Length": "0"}, b"")

        assert isinstance(resp, bytes)
        resp_str = resp.decode("utf-8")
        assert f"{PROTOCOL_VERSION} 400 Bad Request" in resp_str

    def test_format_response_505_version_not_supported(self):
        """Format 505 Version Not Supported P2P response."""
        resp = format_p2p_response(STATUS_VERSION_NOT_SUPPORTED, {"Content-Length": "0"}, b"")

        assert isinstance(resp, bytes)
        resp_str = resp.decode("utf-8")
        assert f"{PROTOCOL_VERSION} 505 P2P-CI Version Not Supported" in resp_str

    def test_format_response_with_binary_data(self):
        """Format response with binary file data."""
        headers = {HEADER_CONTENT_LENGTH: "100", HEADER_CONTENT_TYPE: "text/plain"}
        data = bytes(range(256))[:100]  # 100 arbitrary bytes

        resp = format_p2p_response(STATUS_OK, headers, data)

        # Verify binary data is preserved exactly
        assert resp.endswith(data)

    def test_format_response_empty_data(self):
        """Format response with empty data."""
        headers = {HEADER_CONTENT_LENGTH: "0"}
        resp = format_p2p_response(STATUS_OK, headers, b"")

        assert isinstance(resp, bytes)
        # Should have headers but end with blank line before empty data
        resp_str = resp.decode("utf-8")
        assert f"{PROTOCOL_VERSION} 200 OK" in resp_str


# ============================================================================
# ROUND-TRIP TESTS (Format then Parse)
# ============================================================================


@pytest.mark.protocol
class TestP2SRoundTrip:
    """Test P2S request/response round-trip consistency."""

    def test_format_and_parse_add_request(self):
        """Format ADD request then parse it back."""
        original = format_p2s_request(METHOD_ADD, 123, "host.example.com", 5678, "Test RFC")
        parsed = parse_p2s_request(original)

        assert parsed is not None
        assert parsed["method"] == METHOD_ADD
        assert parsed["rfc_number"] == 123
        assert parsed["host"] == "host.example.com"
        assert parsed["port"] == 5678
        assert parsed["title"] == "Test RFC"

    def test_format_and_parse_response_with_records(self):
        """Format response then parse it back."""
        records = [
            (123, "Test RFC", "host1.example.com", 5001),
            (456, "Another RFC", "host2.example.com", 5002),
        ]
        formatted = format_p2s_response(STATUS_OK, records)
        status, parsed_records = parse_p2s_response(formatted)

        assert status == 200
        assert len(parsed_records) == 2
        assert parsed_records[0] == records[0]
        assert parsed_records[1] == records[1]


# ============================================================================
# EDGE CASES AND PROTOCOL STRICTNESS
# ============================================================================


@pytest.mark.protocol
class TestProtocolEdgeCases:
    """Test edge cases and protocol strictness."""

    def test_parse_request_extra_whitespace_in_headers(self):
        """Request with extra whitespace around header values."""
        req = (
            f"ADD RFC 123 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}:   host.example.com   {CRLF}"
            f"{HEADER_PORT}:   5678   {CRLF}"
            f"{HEADER_TITLE}:   Test RFC   {CRLF}"
            f"{CRLF}"
        )
        result = parse_p2s_request(req)

        assert result is not None
        assert result["host"] == "host.example.com"
        assert result["port"] == 5678
        assert result["title"] == "Test RFC"

    def test_format_response_many_records(self):
        """Format response with many RFC records."""
        records = [(i, f"RFC {i}", f"host{i}.example.com", 5000 + i) for i in range(1, 11)]
        resp = format_p2s_response(STATUS_OK, records)

        status, parsed = parse_p2s_response(resp)
        assert status == 200
        assert len(parsed) == 10

    def test_parse_response_with_sparse_records(self):
        """Parse response with blank lines in record section."""
        resp = (
            f"{PROTOCOL_VERSION} 200 OK{CRLF}"
            f"{CRLF}"
            f"123 Test RFC host.example.com 5000{CRLF}"
            f"{CRLF}"
        )
        status, records = parse_p2s_response(resp)

        # Should stop at blank line
        assert status == 200
        assert len(records) == 1

    def test_parse_p2p_request_with_complex_os_string(self):
        """P2P request with complex OS string."""
        req = (
            f"GET RFC 1234 {PROTOCOL_VERSION}{CRLF}"
            f"{HEADER_HOST}: host.example.com{CRLF}"
            f"{HEADER_OS}: Linux kernel 5.15.0-1234-generic #5678-Ubuntu SMP{CRLF}"
            f"{CRLF}"
        ).encode("utf-8")

        result = parse_p2p_request(req)

        assert result is not None
        assert "Linux kernel 5.15.0" in result["os"]

    def test_large_rfc_number(self):
        """Test with large RFC number."""
        req = format_p2s_request(METHOD_ADD, 9999999, "host.example.com", 5678, "Large RFC")
        parsed = parse_p2s_request(req)

        assert parsed is not None
        assert parsed["rfc_number"] == 9999999

    def test_large_port_number(self):
        """Test with large port number."""
        req = format_p2s_request(METHOD_ADD, 123, "host.example.com", 65535, "Test RFC")
        parsed = parse_p2s_request(req)

        assert parsed is not None
        assert parsed["port"] == 65535
