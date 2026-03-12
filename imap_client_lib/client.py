"""
IMAP client for connecting to email servers and retrieving messages.
"""
from typing import List, Optional, Tuple, Callable
import os
from pathlib import Path
import logging

from imapclient import IMAPClient

from .account import Account
from .email_message import EmailMessage, Attachment
from .smtp_mixin import SmtpMixin
from .draft_mixin import DraftMixin
from .message_ops_mixin import MessageOpsMixin, _extract_keywords


class ImapClient(SmtpMixin, DraftMixin, MessageOpsMixin):
    """
    Handles IMAP connections and email operations.
    """

    def __init__(
        self,
        account: Account,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the IMAP client with an account.

        Args:
            account: The email account configuration
            logger: Optional logger instance
        """
        self.account = account
        self.client = None
        self.logger = logger or logging.getLogger(__name__)

    def connect(self) -> bool:
        """Connect to the IMAP server.

        Returns:
            bool: True if connection was successful
        """
        try:
            self.logger.info(
                f"Connecting to {self.account.server} "
                f"for account {self.account.name}"
            )
            self.client = IMAPClient(
                self.account.server,
                port=self.account.port,
                use_uid=True,
                ssl=self.account.use_ssl,
                timeout=300,
            )
            self.client.login(
                self.account.username,
                self.account.password,
            )
            self.logger.info(
                f"Connected to {self.account.server}"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to connect to "
                f"{self.account.server}: {e}"
            )
            return False

    def disconnect(self):
        """Disconnect from the IMAP server."""
        if self.client:
            try:
                self.client.logout()
                self.logger.info(
                    f"Disconnected from "
                    f"{self.account.server}"
                )
            except Exception as e:
                self.logger.error(
                    f"Error disconnecting from "
                    f"{self.account.server}: {e}"
                )
            finally:
                self.client = None

    def get_messages(
        self,
        search_criteria: List[str] = None,
        folder: str = 'INBOX',
        limit: Optional[int] = None,
        include_attachments: bool = True,
    ) -> List[Tuple[str, EmailMessage]]:
        """Get messages from a folder based on search criteria.

        Args:
            search_criteria: IMAP search criteria
            folder: The folder to search in
            limit: Maximum number of messages to return
            include_attachments: Whether to include attachments

        Returns:
            List of (message_id, EmailMessage) tuples
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return []

        if search_criteria is None:
            search_criteria = ['UNSEEN']

        try:
            self.client.select_folder(folder)

            self.logger.info(
                f"Searching with criteria: "
                f"{search_criteria}"
            )
            message_ids = self.client.search(
                search_criteria
            )

            if not message_ids:
                self.logger.info("No messages found")
                return []

            self.logger.info(
                f"Found {len(message_ids)} messages"
            )

            message_ids = sorted(
                message_ids, reverse=True
            )

            if limit is not None and limit > 0:
                message_ids = message_ids[:limit]
                self.logger.info(
                    f"Limited to {len(message_ids)} "
                    f"most recent messages"
                )

            messages = []
            for message_id in message_ids:
                try:
                    raw_message = self.client.fetch(
                        [message_id],
                        ['BODY.PEEK[]', 'FLAGS'],
                    )
                    message_data = (
                        raw_message[message_id][b'BODY[]']
                    )
                    flags = raw_message[message_id].get(
                        b'FLAGS', ()
                    )
                    keywords = _extract_keywords(flags)
                    email_message = EmailMessage.from_bytes(
                        str(message_id),
                        message_data,
                        self.logger,
                        include_attachments,
                        keywords=keywords,
                    )
                    messages.append(
                        (str(message_id), email_message)
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error fetching message "
                        f"{message_id}: {e}"
                    )

            return messages
        except Exception as e:
            self.logger.error(
                f"Error getting messages: {e}"
            )
            return []

    def get_unread_messages(
        self, include_attachments: bool = True,
    ) -> List[Tuple[str, EmailMessage]]:
        """Get all unread messages from the inbox.

        Args:
            include_attachments: Whether to include
                attachments

        Returns:
            List of (message_id, EmailMessage) tuples
        """
        return self.get_messages(
            ['UNSEEN'], 'INBOX',
            include_attachments=include_attachments,
        )

    def get_all_messages(
        self,
        folder: str = 'INBOX',
        limit: int = 100,
        include_attachments: bool = True,
    ) -> List[Tuple[str, EmailMessage]]:
        """Get all messages from a folder (most recent first).

        Args:
            folder: The folder to get messages from
            limit: Maximum number of messages to return
            include_attachments: Whether to include
                attachments

        Returns:
            List of (message_id, EmailMessage) tuples
        """
        return self.get_messages(
            ['ALL'], folder, limit, include_attachments
        )

    def get_folder_message_count(
        self, folder: str = 'INBOX',
    ) -> Optional[int]:
        """Get the number of messages in a folder.

        Uses IMAP SELECT which returns the EXISTS count.

        Args:
            folder: The folder to check

        Returns:
            The message count, or None on error.
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return None
        try:
            info = self.client.select_folder(folder)
            return info.get(b'EXISTS', None)
        except Exception as e:
            self.logger.error(
                f"Error getting message count "
                f"for '{folder}': {e}"
            )
            return None

    def list_folders(self) -> List[str]:
        """List all folders in the mailbox.

        Returns:
            List[str]: List of folder names
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return []

        try:
            folders = self.client.list_folders()
            folder_names = [f[2] for f in folders]
            return folder_names
        except Exception as e:
            self.logger.error(
                f"Error listing folders: {e}"
            )
            return []

    def idle_start(self, folder: str = 'INBOX') -> bool:
        """Start IDLE mode on a folder.

        IDLE allows the server to push notifications
        about new emails instead of requiring polling.

        Args:
            folder: The folder to monitor

        Returns:
            bool: True if IDLE mode started successfully
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return False

        try:
            self.client.select_folder(folder)
            self.client.idle()
            self.logger.debug(
                f"Started IDLE on folder '{folder}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error starting IDLE mode: {e}"
            )
            return False

    def idle_check(
        self, timeout: int = 30,
    ) -> List[Tuple[int, bytes]]:
        """Check for IDLE responses.

        Blocks until a response is received or timeout.

        Args:
            timeout: Max wait time in seconds

        Returns:
            List of (msg_id, event) tuples.
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return []

        try:
            responses = self.client.idle_check(
                timeout=timeout
            )
            if responses:
                self.logger.debug(
                    f"IDLE responses: {responses}"
                )
            return responses
        except Exception as e:
            self.logger.error(
                f"Error checking IDLE: {e}"
            )
            raise

    def idle_done(self) -> None:
        """Exit IDLE mode.

        Must be called before performing any other IMAP
        operations after starting IDLE mode.
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return

        try:
            self.client.idle_done()
            self.logger.debug("Exited IDLE mode")
        except Exception as e:
            self.logger.error(
                f"Error exiting IDLE mode: {e}"
            )

    def save_attachment(
        self,
        attachment: Attachment,
        target_path: str,
        sanitize_filename: bool = True,
    ) -> str:
        """Save an attachment to disk.

        Args:
            attachment: The attachment to save
            target_path: Directory or full file path
            sanitize_filename: Whether to sanitize filename

        Returns:
            str: Path where file was saved, or empty string
        """
        try:
            if os.path.isdir(target_path) or not (
                os.path.splitext(target_path)[1]
            ):
                target_dir = Path(target_path)
                os.makedirs(target_dir, exist_ok=True)

                filename = attachment.filename
                if sanitize_filename:
                    filename = filename.replace(
                        '/', '_'
                    ).replace('\\', '_')
                    self.logger.debug(
                        f"Sanitized filename: "
                        f"'{attachment.filename}' "
                        f"-> '{filename}'"
                    )

                file_path = target_dir / filename
            else:
                file_path = Path(target_path)
                os.makedirs(
                    file_path.parent, exist_ok=True
                )

            counter = 1
            original_path = file_path
            while file_path.exists():
                name = original_path.stem
                ext = original_path.suffix
                file_path = original_path.parent / f"{name}_{counter}{ext}"
                counter += 1

            with open(file_path, 'wb') as f:
                f.write(attachment.data)

            self.logger.info(
                f"Saved attachment to {file_path}"
            )
            return str(file_path)

        except Exception as e:
            self.logger.error(
                f"Error saving attachment "
                f"{attachment.filename}: {e}"
            )
            return ""

    def process_messages_with_callback(
        self,
        callback: Callable[[EmailMessage], bool],
        search_criteria: List[str] = None,
        folder: str = 'INBOX',
        mark_as_read: bool = True,
        move_to_folder: Optional[str] = None,
    ) -> int:
        """Process messages with a custom callback.

        Args:
            callback: Function taking an EmailMessage,
                returns True to continue processing
            search_criteria: IMAP search criteria
            folder: The folder to search in
            mark_as_read: Mark processed messages as read
            move_to_folder: Folder to move processed msgs

        Returns:
            int: Number of messages processed
        """
        if not self.connect():
            return 0

        try:
            messages = self.get_messages(
                search_criteria, folder
            )
            processed_count = 0

            for message_id, email_message in messages:
                try:
                    if callback(email_message):
                        processed_count += 1

                        if mark_as_read:
                            self.mark_as_read(message_id)

                        if move_to_folder:
                            self.move_to_folder(
                                message_id, move_to_folder
                            )

                except Exception as e:
                    self.logger.error(
                        f"Error processing message "
                        f"{message_id}: {e}"
                    )

            return processed_count

        finally:
            self.disconnect()

    def _ensure_folder_exists(
        self, folder: str,
    ) -> bool:
        """Ensure a folder exists, creating it if needed.

        Args:
            folder: The folder name to check/create

        Returns:
            bool: True if folder exists or was created
        """
        folders = self.client.list_folders()
        folder_names = [f[2] for f in folders]

        if folder not in folder_names:
            self.logger.warning(
                f"Folder '{folder}' does not exist, "
                f"attempting to create it"
            )
            try:
                self.client.create_folder(folder)
                self.logger.info(
                    f"Created folder '{folder}'"
                )
            except Exception as e:
                self.logger.error(
                    f"Error creating folder "
                    f"'{folder}': {e}"
                )
                return False
        return True
