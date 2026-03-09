"""Mixin providing SMTP email sending and forwarding operations."""
from typing import List, Optional, Dict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from .email_message import EmailMessage, Attachment


class SmtpMixin:
    """SMTP operations for ImapClient."""

    def _resolve_smtp_credentials(self, server, user, pw):
        """Resolve SMTP credentials with account fallbacks."""
        if user is None:
            user = self.account.username
        if pw is None:
            pw = self.account.password
        if server is None:
            server = self.account.server.replace(
                'imap', 'smtp'
            )
            self.logger.info(
                f"Derived SMTP server: {server}"
            )
        return server, user, pw

    def _set_message_headers(self, msg, from_email,
                             to_addresses, subject,
                             cc_addresses=None,
                             bcc_addresses=None,
                             custom_headers=None):
        """Set standard email headers on a MIME message."""
        msg['From'] = from_email
        msg['To'] = ', '.join(to_addresses)
        if cc_addresses:
            msg['Cc'] = ', '.join(cc_addresses)
        if bcc_addresses:
            msg['Bcc'] = ', '.join(bcc_addresses)
        msg['Subject'] = subject
        if custom_headers:
            for hdr_name, hdr_val in custom_headers.items():
                if hdr_name in msg:
                    del msg[hdr_name]
                msg[hdr_name] = hdr_val

    def _log_send_success(self, action, to_addresses,
                          bcc_addresses=None):
        """Log a successful send/forward operation."""
        log_msg = (
            f"Successfully {action} email to: "
            f"{', '.join(to_addresses)}"
        )
        if bcc_addresses:
            log_msg += (
                f" (BCC: {', '.join(bcc_addresses)})"
            )
        self.logger.info(log_msg)

    def _smtp_send(
        self,
        msg: MIMEMultipart,
        to_addresses: List[str],
        bcc_addresses: Optional[List[str]] = None,
        smtp_server: Optional[str] = None,
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
    ) -> bool:
        """Send an already-built MIME message via SMTP."""
        smtp_server, smtp_username, smtp_password = (
            self._resolve_smtp_credentials(
                smtp_server, smtp_username, smtp_password,
            )
        )
        self.logger.info(
            f"Connecting to SMTP: {smtp_server}:{smtp_port}"
        )
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            all_recipients = to_addresses.copy()
            if bcc_addresses:
                all_recipients.extend(bcc_addresses)
            server.send_message(
                msg, to_addrs=all_recipients
            )
        return True

    def send_email(
        self,
        to_addresses: List[str],
        subject: str,
        body: str,
        content_type: str = "text/plain",
        from_email: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        attachments: Optional[List[Attachment]] = None,
        smtp_server: Optional[str] = None,
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
    ) -> bool:
        """Send a new email via SMTP."""
        try:
            if from_email is None:
                from_email = self.account.username
            has_attachments = (
                attachments and len(attachments) > 0
            )
            has_inline_images = has_attachments and any(
                att.is_inline and att.content_id
                for att in attachments
            )
            if has_inline_images:
                msg = MIMEMultipart('related')
            elif has_attachments:
                msg = MIMEMultipart('mixed')
            elif content_type == "text/html":
                msg = MIMEMultipart('alternative')
            else:
                msg = MIMEMultipart()
            self._set_message_headers(
                msg, from_email, to_addresses, subject,
                cc_addresses, bcc_addresses, custom_headers,
            )
            if has_inline_images and content_type == "text/html":
                alternative = MIMEMultipart('alternative')
                alternative.attach(MIMEText(body, 'plain'))
                alternative.attach(MIMEText(body, 'html'))
                msg.attach(alternative)
            else:
                sub_type = content_type.split('/')[-1]
                msg.attach(MIMEText(body, sub_type))
            if attachments:
                self._attach_files(msg, attachments)
            self._smtp_send(
                msg, to_addresses, bcc_addresses,
                smtp_server, smtp_port,
                smtp_username, smtp_password,
            )
            self._log_send_success(
                "sent", to_addresses, bcc_addresses,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error sending email: {e}")
            return False

    def forward_email(
        self,
        email_message: EmailMessage,
        to_addresses: List[str],
        new_subject: Optional[str] = None,
        smtp_server: Optional[str] = None,
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        sender_email: Optional[str] = None,
        bcc_addresses: Optional[List[str]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        additional_message: str = "",
    ) -> bool:
        """Forward an email with an optional modified subject."""
        try:
            if new_subject is None:
                new_subject = f"Fwd: {email_message.subject}"
            if sender_email is None:
                sender_email = (
                    smtp_username
                    if smtp_username is not None
                    else self.account.username
                )
            has_inline = any(
                att.is_inline and att.content_id
                for att in email_message.attachments
            )
            msg = MIMEMultipart(
                'related' if has_inline else 'mixed'
            )
            self._set_message_headers(
                msg, sender_email, to_addresses,
                new_subject, bcc_addresses=bcc_addresses,
                custom_headers=custom_headers,
            )
            self._build_forward_body(
                msg, has_inline, email_message,
                additional_message,
            )
            self._attach_files(
                msg, email_message.attachments
            )
            self._smtp_send(
                msg, to_addresses, bcc_addresses,
                smtp_server, smtp_port,
                smtp_username, smtp_password,
            )
            self._log_send_success(
                "forwarded", to_addresses, bcc_addresses,
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error forwarding email: {e}"
            )
            return False

    def _build_forward_body(self, msg, has_inline,
                            email_message,
                            additional_message):
        """Build the forwarded email body content."""
        orig_text = (
            email_message.get_body('text/plain') or ""
        )
        orig_html = (
            email_message.get_body('text/html') or ""
        )
        fwd_header = (
            f"\n---------- Forwarded message "
            f"----------\n"
            f"From: {email_message.from_address}\n"
            f"Date: {email_message.date}\n"
            f"Subject: {email_message.subject}\n\n"
        )
        if additional_message:
            fwd_content = (
                f"{additional_message}\n\n"
                f"{fwd_header}{orig_text}"
            )
        else:
            fwd_content = f"{fwd_header}{orig_text}"
        fwd_info = (
            f"<p>---------- Forwarded message "
            f"----------<br>\n"
            f"From: {email_message.from_address}<br>\n"
            f"Date: {email_message.date}<br>\n"
            f"Subject: {email_message.subject}</p>\n"
            f"<div>{orig_html}</div>"
        )
        if additional_message:
            am_html = additional_message.replace(
                chr(10), '<br>'
            )
            html_fwd = (
                f"<p>{am_html}</p>\n<div>{fwd_info}</div>"
            )
        else:
            html_fwd = f"<div>{fwd_info}</div>"
        if has_inline and orig_html:
            alt = MIMEMultipart('alternative')
            alt.attach(MIMEText(fwd_content, 'plain'))
            alt.attach(MIMEText(html_fwd, 'html'))
            msg.attach(alt)
        else:
            msg.attach(MIMEText(fwd_content, 'plain'))
            if orig_html:
                msg.attach(MIMEText(html_fwd, 'html'))

    def _attach_files(self, msg, attachments):
        """Attach files (inline or regular) to a message."""
        for attachment in attachments:
            if attachment.is_inline and attachment.content_id:
                main_type, sub_type = (
                    attachment.content_type.split('/', 1)
                )
                part = MIMEBase(main_type, sub_type)
                part.set_payload(attachment.data)
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition', 'inline',
                    filename=attachment.filename,
                )
                cid = attachment.content_id.strip('<>')
                part.add_header('Content-ID', f'<{cid}>')
                msg.attach(part)
                self.logger.debug(
                    f"Attached inline image: "
                    f"{attachment.filename} "
                    f"with Content-ID: <{cid}>"
                )
            else:
                part = MIMEBase(
                    'application', 'octet-stream'
                )
                part.set_payload(attachment.data)
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= '
                    f'{attachment.filename}',
                )
                msg.attach(part)
                self.logger.debug(
                    f"Attached file: {attachment.filename}"
                )
