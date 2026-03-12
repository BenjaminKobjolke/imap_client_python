"""Integration tests for IMAP keyword (tag) operations.

Requires a live IMAP account configured in .env.
Run with: python -m pytest tests/test_integration_keywords.py -v
"""

from __future__ import annotations

import pytest

from imap_client_lib.client import ImapClient
from tests.conftest import requires_imap

pytestmark = [pytest.mark.integration, requires_imap]

# Keyword used as a scratch tag during tests.
_TEST_KEYWORD = "$label5"
# Thunderbird "Important" tag.
_TB_IMPORTANT = "$label1"


def _get_first_message_id(client: ImapClient) -> str:
    """Select INBOX and return the UID of the most recent message."""
    client.client.select_folder("INBOX")
    uids = client.client.search(["ALL"])
    if not uids:
        pytest.skip("INBOX is empty – need at least one message")
    return str(max(uids))


class TestConnection:
    """Basic connectivity smoke tests."""

    def test_connect(self, imap_client: ImapClient) -> None:
        """Verify we can connect and the client is alive."""
        assert imap_client.client is not None

    def test_list_folders(
        self, imap_client: ImapClient,
    ) -> None:
        """Verify folder listing works."""
        folders = imap_client.list_folders()
        assert isinstance(folders, list)
        assert len(folders) > 0


class TestKeywordOperations:
    """Add / get / remove keyword tests."""

    def test_add_and_get_keyword(
        self, imap_client: ImapClient,
    ) -> None:
        """Add a keyword then read it back."""
        uid = _get_first_message_id(imap_client)
        try:
            assert imap_client.add_keyword(uid, _TEST_KEYWORD)
            keywords = imap_client.get_keywords(uid)
            assert _TEST_KEYWORD in keywords
        finally:
            imap_client.remove_keyword(uid, _TEST_KEYWORD)

    def test_remove_keyword(
        self, imap_client: ImapClient,
    ) -> None:
        """Add then remove a keyword, verify it's gone."""
        uid = _get_first_message_id(imap_client)
        try:
            imap_client.add_keyword(uid, _TEST_KEYWORD)
            assert imap_client.remove_keyword(
                uid, _TEST_KEYWORD,
            )
            keywords = imap_client.get_keywords(uid)
            assert _TEST_KEYWORD not in keywords
        finally:
            imap_client.remove_keyword(uid, _TEST_KEYWORD)

    def test_get_messages_includes_keywords(
        self, imap_client: ImapClient,
    ) -> None:
        """Fetch messages via get_messages and check keywords."""
        uid = _get_first_message_id(imap_client)
        try:
            imap_client.add_keyword(uid, _TEST_KEYWORD)
            messages = imap_client.get_messages(
                search_criteria=["ALL"],
                folder="INBOX",
                limit=5,
                include_attachments=False,
            )
            assert len(messages) > 0
            matched = [
                msg for mid, msg in messages
                if mid == uid
            ]
            assert len(matched) == 1
            assert _TEST_KEYWORD in matched[0].keywords
        finally:
            imap_client.remove_keyword(uid, _TEST_KEYWORD)

    def test_keyword_roundtrip(
        self, imap_client: ImapClient,
    ) -> None:
        """Full roundtrip: add $label1, read, remove, confirm."""
        uid = _get_first_message_id(imap_client)
        try:
            # Add Thunderbird "Important" tag.
            assert imap_client.add_keyword(uid, _TB_IMPORTANT)

            keywords = imap_client.get_keywords(uid)
            assert _TB_IMPORTANT in keywords

            # Remove it.
            assert imap_client.remove_keyword(
                uid, _TB_IMPORTANT,
            )

            keywords = imap_client.get_keywords(uid)
            assert _TB_IMPORTANT not in keywords
        finally:
            imap_client.remove_keyword(uid, _TB_IMPORTANT)
