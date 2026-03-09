"""
Mixin providing draft email operations.
"""
from typing import List, Optional, Dict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .email_message import Attachment


class DraftMixin:
    """Draft email operations for ImapClient."""

    def save_draft(
        self,
        to_addresses: List[str],
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        content_type: str = "text/plain",
        attachments: Optional[List[Attachment]] = None,
        draft_folder: str = "Drafts",
        mark_as_unread: bool = True,
    ) -> bool:
        """Save a draft email to the drafts folder.

        Args:
            to_addresses: List of recipient email addresses
            subject: Email subject line
            body: Email body content
            from_email: Sender email address
            cc_addresses: List of CC email addresses
            bcc_addresses: List of BCC email addresses
            custom_headers: Dictionary of custom headers
            content_type: Content type
            attachments: List of Attachment objects
            draft_folder: Name of the drafts folder
            mark_as_unread: Mark the draft as unread

        Returns:
            bool: True if draft was saved successfully
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return False

        try:
            if from_email is None:
                from_email = self.account.username

            has_attachments = (
                attachments and len(attachments) > 0
            )
            has_inline = has_attachments and any(
                att.is_inline and att.content_id
                for att in attachments
            )

            if has_inline:
                msg = MIMEMultipart('related')
            elif has_attachments:
                msg = MIMEMultipart('mixed')
            else:
                msg = MIMEMultipart()

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
                        self.logger.debug(
                            f"Removed header: {hdr_name}"
                        )
                    msg[hdr_name] = hdr_val
                    self.logger.debug(
                        f"Added header: "
                        f"{hdr_name}: {hdr_val}"
                    )

            if has_inline and content_type == "text/html":
                alternative = MIMEMultipart('alternative')
                alternative.attach(
                    MIMEText(body, 'plain')
                )
                alternative.attach(
                    MIMEText(body, 'html')
                )
                msg.attach(alternative)
            else:
                sub_type = content_type.split('/')[-1]
                msg.attach(MIMEText(body, sub_type))

            if attachments:
                self._attach_files(msg, attachments)

            if not self._ensure_folder_exists(draft_folder):
                return False

            message_bytes = msg.as_bytes()

            flags = [b'\\Draft']
            if not mark_as_unread:
                flags.append(b'\\Seen')

            self.logger.debug(
                f"Saving draft to '{draft_folder}' "
                f"with flags: {flags}"
            )
            result = self.client.append(
                draft_folder, message_bytes, flags=flags
            )

            if result:
                self.logger.info(
                    f"Saved draft to '{draft_folder}'"
                )
                return True
            else:
                self.logger.error(
                    f"Failed to save draft "
                    f"to '{draft_folder}'"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"Error saving draft: {e}"
            )
            return False

    def update_draft(
        self,
        message_id: str,
        to_addresses: List[str],
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        content_type: str = "text/plain",
        attachments: Optional[List[Attachment]] = None,
        draft_folder: str = "Drafts",
        mark_as_unread: bool = True,
    ) -> bool:
        """Update an existing draft by replacing it.

        Args:
            message_id: The ID of the draft to update
            to_addresses: List of recipient email addresses
            subject: Email subject line
            body: Email body content
            from_email: Sender email address
            cc_addresses: List of CC email addresses
            bcc_addresses: List of BCC email addresses
            custom_headers: Dictionary of custom headers
            content_type: Content type
            attachments: List of Attachment objects
            draft_folder: Name of the drafts folder
            mark_as_unread: Mark the draft as unread

        Returns:
            bool: True if draft was updated successfully
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return False

        try:
            self.client.select_folder(draft_folder)

            try:
                msg_data = self.client.fetch(
                    [int(message_id)], ['FLAGS']
                )
                if int(message_id) not in msg_data:
                    self.logger.error(
                        f"Draft {message_id} not found "
                        f"in '{draft_folder}'"
                    )
                    return False

                flags = msg_data[int(message_id)][b'FLAGS']
                if b'\\Draft' not in flags:
                    self.logger.warning(
                        f"Message {message_id} has no "
                        f"\\Draft flag. Proceeding anyway."
                    )

            except Exception as e:
                self.logger.error(
                    f"Error checking draft "
                    f"{message_id}: {e}"
                )
                return False

            self.logger.debug(
                f"Creating updated draft for "
                f"message {message_id}"
            )
            draft_saved = self.save_draft(
                to_addresses=to_addresses,
                subject=subject,
                body=body,
                from_email=from_email,
                cc_addresses=cc_addresses,
                bcc_addresses=bcc_addresses,
                custom_headers=custom_headers,
                content_type=content_type,
                attachments=attachments,
                draft_folder=draft_folder,
                mark_as_unread=mark_as_unread,
            )

            if not draft_saved:
                self.logger.error(
                    "Failed to save updated draft content"
                )
                return False

            self.logger.debug(
                f"Deleting old draft {message_id}"
            )
            try:
                self.client.delete_messages(
                    [int(message_id)]
                )
                self.client.expunge()
                self.logger.info(
                    f"Updated draft (deleted old "
                    f"message {message_id})"
                )
                return True
            except Exception as e:
                self.logger.error(
                    f"Error deleting old draft "
                    f"{message_id}: {e}"
                )
                self.logger.warning(
                    "Updated draft was saved, but "
                    "old draft could not be deleted"
                )
                return True

        except Exception as e:
            self.logger.error(
                f"Error updating draft: {e}"
            )
            return False
