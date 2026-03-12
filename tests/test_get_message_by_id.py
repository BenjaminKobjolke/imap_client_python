"""Tests for ImapClient.get_message_by_id()."""

from __future__ import annotations

from unittest.mock import MagicMock

from imap_client_lib.account import Account
from imap_client_lib.client import ImapClient


def _make_client() -> ImapClient:
    """Create an ImapClient with a mocked IMAP backend."""
    account = Account(
        name="test",
        server="imap.example.com",
        username="user@example.com",
        password="secret",
    )
    client = ImapClient(account)
    client.client = MagicMock()
    return client


_RAW_EMAIL = (
    b"From: sender@example.com\r\n"
    b"Subject: Hello\r\n"
    b"Date: Mon, 01 Jan 2024 00:00:00 +0000\r\n"
    b"\r\nBody text"
)


class TestGetMessageById:
    """Tests for the get_message_by_id method."""

    def test_returns_message(self) -> None:
        """Returns (id, EmailMessage) for a valid UID."""
        client = _make_client()
        client.client.fetch.return_value = {
            456: {
                b'BODY[]': _RAW_EMAIL,
                b'FLAGS': (b'\\Seen', b'$label1'),
            },
        }

        result = client.get_message_by_id("456", folder="INBOX")

        client.client.select_folder.assert_called_once_with(
            "INBOX"
        )
        client.client.fetch.assert_called_once_with(
            [456], ['BODY.PEEK[]', 'FLAGS'],
        )
        assert result is not None
        msg_id, email_msg = result
        assert msg_id == "456"
        assert email_msg.subject == "Hello"
        assert email_msg.keywords == ['$label1']

    def test_returns_none_when_uid_not_found(self) -> None:
        """Returns None when the UID is not in fetch result."""
        client = _make_client()
        client.client.fetch.return_value = {}

        result = client.get_message_by_id("999")

        assert result is None

    def test_returns_none_on_error(self) -> None:
        """Returns None when fetch raises an exception."""
        client = _make_client()
        client.client.fetch.side_effect = Exception(
            "fetch failed"
        )

        result = client.get_message_by_id("456")

        assert result is None

    def test_returns_none_when_not_connected(self) -> None:
        """Returns None when not connected."""
        client = _make_client()
        client.client = None

        result = client.get_message_by_id("456")

        assert result is None

    def test_custom_folder(self) -> None:
        """Selects the specified folder."""
        client = _make_client()
        client.client.fetch.return_value = {
            10: {
                b'BODY[]': _RAW_EMAIL,
                b'FLAGS': (),
            },
        }

        result = client.get_message_by_id(
            "10", folder="Sent"
        )

        client.client.select_folder.assert_called_once_with(
            "Sent"
        )
        assert result is not None
        assert result[0] == "10"

    def test_no_attachments(self) -> None:
        """Passes include_attachments through."""
        client = _make_client()
        client.client.fetch.return_value = {
            7: {
                b'BODY[]': _RAW_EMAIL,
                b'FLAGS': (),
            },
        }

        result = client.get_message_by_id(
            "7", include_attachments=False,
        )

        assert result is not None
