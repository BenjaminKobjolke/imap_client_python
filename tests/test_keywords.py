"""Tests for IMAP keyword (tag) operations."""

from __future__ import annotations

from unittest.mock import MagicMock

from imap_client_lib.account import Account
from imap_client_lib.client import ImapClient
from imap_client_lib.email_message import EmailMessage
from imap_client_lib.message_ops_mixin import _extract_keywords


def _make_client() -> ImapClient:
    """Create an ImapClient with a test account."""
    account = Account(
        name="test",
        server="imap.example.com",
        username="user@example.com",
        password="secret",
    )
    client = ImapClient(account)
    client.client = MagicMock()
    return client


class TestExtractKeywords:
    """Tests for the _extract_keywords helper."""

    def test_filters_system_flags(self) -> None:
        """System flags (starting with \\) are excluded."""
        flags = (b'\\Seen', b'\\Flagged', b'$label1')
        assert _extract_keywords(flags) == ['$label1']

    def test_returns_multiple_keywords(self) -> None:
        """Multiple custom keywords are returned."""
        flags = (
            b'\\Seen', b'$label1',
            b'$label2', b'custom_tag',
        )
        result = _extract_keywords(flags)
        assert result == ['$label1', '$label2', 'custom_tag']

    def test_empty_flags(self) -> None:
        """Empty flags tuple returns empty list."""
        assert _extract_keywords(()) == []

    def test_only_system_flags(self) -> None:
        """Only system flags returns empty list."""
        flags = (b'\\Seen', b'\\Answered', b'\\Draft')
        assert _extract_keywords(flags) == []

    def test_handles_string_flags(self) -> None:
        """Handles flags that are already strings."""
        flags = ('\\Seen', '$label1')
        assert _extract_keywords(flags) == ['$label1']


class TestGetKeywords:
    """Tests for ImapClient.get_keywords()."""

    def test_returns_keywords(self) -> None:
        """Returns non-system keywords from message."""
        client = _make_client()
        client.client.fetch.return_value = {
            123: {
                b'FLAGS': (
                    b'\\Seen', b'$label1', b'$label3',
                ),
            },
        }

        result = client.get_keywords("123")

        client.client.fetch.assert_called_once_with(
            [123], ['FLAGS']
        )
        assert result == ['$label1', '$label3']

    def test_returns_empty_when_no_keywords(self) -> None:
        """Returns empty list when no custom keywords."""
        client = _make_client()
        client.client.fetch.return_value = {
            123: {b'FLAGS': (b'\\Seen',)},
        }

        assert client.get_keywords("123") == []

    def test_returns_empty_on_error(self) -> None:
        """Returns empty list on fetch error."""
        client = _make_client()
        client.client.fetch.side_effect = Exception(
            "fetch failed"
        )

        assert client.get_keywords("123") == []

    def test_returns_empty_when_not_connected(self) -> None:
        """Returns empty list when not connected."""
        client = _make_client()
        client.client = None

        assert client.get_keywords("123") == []


class TestAddKeyword:
    """Tests for ImapClient.add_keyword()."""

    def test_adds_keyword(self) -> None:
        """Adds keyword via add_flags."""
        client = _make_client()

        result = client.add_keyword("123", "$label1")

        assert result is True
        client.client.add_flags.assert_called_once_with(
            [123], [b'$label1']
        )

    def test_returns_false_on_error(self) -> None:
        """Returns False when add_flags raises."""
        client = _make_client()
        client.client.add_flags.side_effect = Exception(
            "failed"
        )

        assert client.add_keyword("123", "$label1") is False

    def test_returns_false_when_not_connected(self) -> None:
        """Returns False when not connected."""
        client = _make_client()
        client.client = None

        assert client.add_keyword("123", "$label1") is False


class TestRemoveKeyword:
    """Tests for ImapClient.remove_keyword()."""

    def test_removes_keyword(self) -> None:
        """Removes keyword via remove_flags."""
        client = _make_client()

        result = client.remove_keyword("123", "$label1")

        assert result is True
        client.client.remove_flags.assert_called_once_with(
            [123], [b'$label1']
        )

    def test_returns_false_on_error(self) -> None:
        """Returns False when remove_flags raises."""
        client = _make_client()
        client.client.remove_flags.side_effect = Exception(
            "failed"
        )

        result = client.remove_keyword("123", "$label1")
        assert result is False

    def test_returns_false_when_not_connected(self) -> None:
        """Returns False when not connected."""
        client = _make_client()
        client.client = None

        result = client.remove_keyword("123", "$label1")
        assert result is False


class TestEmailMessageKeywords:
    """Tests for keywords in EmailMessage model."""

    def test_keywords_default_empty(self) -> None:
        """Keywords default to empty list."""
        msg = EmailMessage(
            message_id="1",
            from_address="test@example.com",
            subject="Test",
            date="2024-01-01",
            attachments=[],
            raw_message=MagicMock(),
        )
        assert msg.keywords == []

    def test_keywords_from_bytes(self) -> None:
        """Keywords are passed through from_bytes."""
        raw = (
            b"From: test@example.com\r\n"
            b"Subject: Test\r\n"
            b"Date: Mon, 01 Jan 2024 00:00:00 +0000\r\n"
            b"\r\nBody"
        )
        msg = EmailMessage.from_bytes(
            "1", raw,
            keywords=['$label1', '$label2'],
        )
        assert msg.keywords == ['$label1', '$label2']

    def test_keywords_none_becomes_empty(self) -> None:
        """Passing None keywords results in empty list."""
        raw = (
            b"From: test@example.com\r\n"
            b"Subject: Test\r\n"
            b"\r\nBody"
        )
        msg = EmailMessage.from_bytes("1", raw)
        assert msg.keywords == []
