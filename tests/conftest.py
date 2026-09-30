"""Shared test fixtures."""

import socket
from typing import NoReturn

import pytest


@pytest.fixture(autouse=True)
def block_network_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent unit tests from making outbound socket connections."""

    def reject_connection(*args: object, **kwargs: object) -> NoReturn:
        raise RuntimeError("Network access is disabled during tests.")

    monkeypatch.setattr(socket, "create_connection", reject_connection)
    monkeypatch.setattr(socket.socket, "connect", reject_connection)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_connection)
