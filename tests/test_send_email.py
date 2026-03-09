"""Tests for ImapClient.send_email() and _smtp_send() methods."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from imap_client_lib.account import Account
from imap_client_lib.client import ImapClient
from imap_client_lib.email_message import Attachment


def _make_client() -> ImapClient:
    """Create an ImapClient with a test account."""
    account = Account(
        name="test",
        server="imap.example.com",
        username="user@example.com",
        password="secret",
    )
    return ImapClient(account)


class TestSmtpSend:
    """Tests for the _smtp_send() helper."""

    @patch("imap_client_lib.smtp_mixin.smtplib.SMTP")
    def test_derives_smtp_server_from_imap(self, mock_smtp_cls: MagicMock) -> None:
        """When smtp_server is None, derives from IMAP server."""
        client = _make_client()
        msg = MagicMock()

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        client._smtp_send(msg, ["to@example.com"])

        mock_smtp_cls.assert_called_once_with("smtp.example.com", 587)

    @patch("imap_client_lib.smtp_mixin.smtplib.SMTP")
    def test_uses_explicit_credentials(self, mock_smtp_cls: MagicMock) -> None:
        """Explicit SMTP params override account defaults."""
        client = _make_client()
        msg = MagicMock()

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        client._smtp_send(
            msg, ["to@example.com"],
            smtp_server="custom.smtp.com",
            smtp_port=465,
            smtp_username="custom_user",
            smtp_password="custom_pass",
        )

        mock_smtp_cls.assert_called_once_with("custom.smtp.com", 465)
        mock_server.login.assert_called_once_with("custom_user", "custom_pass")

    @patch("imap_client_lib.smtp_mixin.smtplib.SMTP")
    def test_includes_bcc_in_recipients(self, mock_smtp_cls: MagicMock) -> None:
        """BCC addresses are added to all_recipients."""
        client = _make_client()
        msg = MagicMock()

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        client._smtp_send(
            msg, ["to@example.com"],
            bcc_addresses=["bcc@example.com"],
        )

        mock_server.send_message.assert_called_once_with(
            msg, to_addrs=["to@example.com", "bcc@example.com"],
        )


class TestSendEmail:
    """Tests for ImapClient.send_email()."""

    @patch("imap_client_lib.smtp_mixin.smtplib.SMTP")
    def test_send_plain_text(self, mock_smtp_cls: MagicMock) -> None:
        """Sends a plain-text email successfully."""
        client = _make_client()

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = client.send_email(
            to_addresses=["recipient@example.com"],
            subject="Test Subject",
            body="Hello, world!",
        )

        assert result is True
        mock_server.send_message.assert_called_once()

    @patch("imap_client_lib.smtp_mixin.smtplib.SMTP")
    def test_send_html(self, mock_smtp_cls: MagicMock) -> None:
        """Sends an HTML email successfully."""
        client = _make_client()

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = client.send_email(
            to_addresses=["recipient@example.com"],
            subject="HTML Test",
            body="<h1>Hello</h1>",
            content_type="text/html",
        )

        assert result is True

    @patch("imap_client_lib.smtp_mixin.smtplib.SMTP")
    def test_send_with_cc_and_bcc(self, mock_smtp_cls: MagicMock) -> None:
        """CC and BCC addresses are included."""
        client = _make_client()

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = client.send_email(
            to_addresses=["to@example.com"],
            subject="Test",
            body="Body",
            cc_addresses=["cc@example.com"],
            bcc_addresses=["bcc@example.com"],
        )

        assert result is True
        # BCC should be in send_message recipients
        send_call = mock_server.send_message.call_args
        to_addrs = send_call.kwargs.get(
            "to_addrs", send_call[1].get("to_addrs", [])
        )
        assert "bcc@example.com" in to_addrs

    @patch("imap_client_lib.smtp_mixin.smtplib.SMTP")
    def test_send_with_custom_headers(self, mock_smtp_cls: MagicMock) -> None:
        """Custom headers are added to the message."""
        client = _make_client()

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = client.send_email(
            to_addresses=["to@example.com"],
            subject="Test",
            body="Body",
            custom_headers={"X-Custom": "value"},
        )

        assert result is True

    @patch("imap_client_lib.smtp_mixin.smtplib.SMTP")
    def test_send_with_attachment(self, mock_smtp_cls: MagicMock) -> None:
        """Email with attachment sends successfully."""
        client = _make_client()

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        attachment = Attachment(
            filename="test.txt",
            content_type="text/plain",
            data=b"file content",
        )

        result = client.send_email(
            to_addresses=["to@example.com"],
            subject="With Attachment",
            body="See attached.",
            attachments=[attachment],
        )

        assert result is True

    @patch("imap_client_lib.smtp_mixin.smtplib.SMTP")
    def test_send_failure_returns_false(self, mock_smtp_cls: MagicMock) -> None:
        """Returns False when SMTP raises an exception."""
        client = _make_client()
        mock_smtp_cls.side_effect = Exception("Connection refused")

        result = client.send_email(
            to_addresses=["to@example.com"],
            subject="Fail Test",
            body="Should fail",
        )

        assert result is False

    @patch("imap_client_lib.smtp_mixin.smtplib.SMTP")
    def test_from_email_defaults_to_account(self, mock_smtp_cls: MagicMock) -> None:
        """from_email defaults to account username when not provided."""
        client = _make_client()

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = client.send_email(
            to_addresses=["to@example.com"],
            subject="Test",
            body="Body",
        )

        assert result is True
        # The message passed to send_message should have From = account username
        sent_msg = mock_server.send_message.call_args[0][0]
        assert sent_msg["From"] == "user@example.com"

    @patch("imap_client_lib.smtp_mixin.smtplib.SMTP")
    def test_explicit_from_email(self, mock_smtp_cls: MagicMock) -> None:
        """Explicit from_email is used when provided."""
        client = _make_client()

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = client.send_email(
            to_addresses=["to@example.com"],
            subject="Test",
            body="Body",
            from_email="sender@other.com",
        )

        assert result is True
        sent_msg = mock_server.send_message.call_args[0][0]
        assert sent_msg["From"] == "sender@other.com"
