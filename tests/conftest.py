"""
Pytest configuration and shared fixtures for project_1 tests.
"""

import pytest


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "protocol: marks tests as protocol parsing/formatting tests"
    )
    config.addinivalue_line(
        "markers", "server: marks tests as server handler tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
