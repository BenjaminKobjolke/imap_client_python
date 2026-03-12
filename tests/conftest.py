"""Shared fixtures for integration tests."""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from imap_client_lib.account import Account
from imap_client_lib.client import ImapClient

load_dotenv()

_IMAP_SERVER = os.getenv("IMAP_SERVER")
_IMAP_USER = os.getenv("IMAP_USER")
_IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")
_IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

_HAS_CREDENTIALS = all([_IMAP_SERVER, _IMAP_USER, _IMAP_PASSWORD])

requires_imap = pytest.mark.skipif(
    not _HAS_CREDENTIALS,
    reason="IMAP credentials not set in .env",
)


@pytest.fixture()
def imap_account() -> Account:
    """Build an Account from environment variables."""
    return Account(
        name="integration-test",
        server=_IMAP_SERVER,
        username=_IMAP_USER,
        password=_IMAP_PASSWORD,
        port=_IMAP_PORT,
    )


@pytest.fixture()
def imap_client(imap_account: Account) -> ImapClient:
    """Yield a connected ImapClient; disconnect on teardown."""
    client = ImapClient(imap_account)
    connected = client.connect()
    if not connected:
        pytest.skip("Could not connect to IMAP server")
    yield client
    client.disconnect()
