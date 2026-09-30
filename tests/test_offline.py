"""Tests for the offline test-runner guarantee."""

import socket

import pytest


def test_network_connections_are_blocked() -> None:
    """Fail locally before any attempted outbound socket connection."""
    with pytest.raises(RuntimeError, match="Network access is disabled during tests"):
        socket.create_connection(("127.0.0.1", 1))
