"""
Mixin providing message management operations.
"""
from typing import List, Optional, Dict
import email


def _extract_keywords(flags: tuple) -> List[str]:
    """Extract non-system keywords from IMAP flags.

    Filters out standard IMAP system flags (starting with
    backslash) and returns only custom keywords/tags.

    Args:
        flags: Tuple of flags from IMAP server

    Returns:
        List of keyword strings
    """
    keywords = []
    for flag in flags:
        flag_str = (
            flag.decode()
            if isinstance(flag, bytes)
            else str(flag)
        )
        if not flag_str.startswith('\\'):
            keywords.append(flag_str)
    return keywords


class MessageOpsMixin:
    """Message management operations for ImapClient."""

    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read.

        Args:
            message_id: The ID of the message

        Returns:
            bool: True if successful
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return False

        try:
            self.client.add_flags(
                [int(message_id)], [b'\\Seen']
            )
            self.logger.info(
                f"Marked message {message_id} as read"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error marking message "
                f"{message_id} as read: {e}"
            )
            return False

    def mark_as_unread(self, message_id: str) -> bool:
        """Mark a message as unread.

        Args:
            message_id: The ID of the message

        Returns:
            bool: True if successful
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return False

        try:
            self.client.remove_flags(
                [int(message_id)], [b'\\Seen']
            )
            self.logger.info(
                f"Marked message {message_id} as unread"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error marking message "
                f"{message_id} as unread: {e}"
            )
            return False

    def get_keywords(
        self, message_id: str,
    ) -> List[str]:
        """Get custom keywords (tags) on a message.

        Returns only non-system flags (e.g. Thunderbird
        tags like $label1, $label2).

        Args:
            message_id: The ID of the message

        Returns:
            List of keyword strings, empty on error
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return []

        try:
            result = self.client.fetch(
                [int(message_id)], ['FLAGS']
            )
            flags = result[int(message_id)][b'FLAGS']
            keywords = _extract_keywords(flags)
            self.logger.debug(
                f"Keywords for message {message_id}: "
                f"{keywords}"
            )
            return keywords
        except Exception as e:
            self.logger.error(
                f"Error getting keywords for message "
                f"{message_id}: {e}"
            )
            return []

    def add_keyword(
        self, message_id: str, keyword: str,
    ) -> bool:
        """Add a keyword (tag) to a message.

        Args:
            message_id: The ID of the message
            keyword: The keyword to add (e.g. '$label1')

        Returns:
            bool: True if successful
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return False

        try:
            self.client.add_flags(
                [int(message_id)],
                [keyword.encode()],
            )
            self.logger.info(
                f"Added keyword '{keyword}' to "
                f"message {message_id}"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error adding keyword '{keyword}' "
                f"to message {message_id}: {e}"
            )
            return False

    def remove_keyword(
        self, message_id: str, keyword: str,
    ) -> bool:
        """Remove a keyword (tag) from a message.

        Args:
            message_id: The ID of the message
            keyword: The keyword to remove (e.g. '$label1')

        Returns:
            bool: True if successful
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return False

        try:
            self.client.remove_flags(
                [int(message_id)],
                [keyword.encode()],
            )
            self.logger.info(
                f"Removed keyword '{keyword}' from "
                f"message {message_id}"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error removing keyword '{keyword}' "
                f"from message {message_id}: {e}"
            )
            return False

    def move_to_folder(
        self,
        message_id: str,
        folder: str,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Move a message to a different folder.

        Args:
            message_id: The ID of the message to move
            folder: The destination folder
            custom_headers: Optional custom headers to add

        Returns:
            bool: True if successful
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return False

        if not folder:
            self.logger.debug(
                f"No move folder specified for "
                f"message {message_id}, skipping"
            )
            return True

        if custom_headers:
            return self.move_with_headers(
                message_id, folder, custom_headers
            )

        try:
            if not self._ensure_folder_exists(folder):
                return False

            self.client.move([int(message_id)], folder)
            self.logger.info(
                f"Moved message {message_id} "
                f"to folder '{folder}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error moving message {message_id} "
                f"to folder '{folder}': {e}"
            )
            return False

    def move_message(
        self,
        message_id: str,
        destination_folder: str,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Move a message from current folder to another.

        Args:
            message_id: The ID of the message to move
            destination_folder: The destination folder name
            custom_headers: Optional custom headers to add

        Returns:
            bool: True if successful
        """
        return self.move_to_folder(
            message_id, destination_folder, custom_headers
        )

    def move_with_headers(
        self,
        message_id: str,
        destination_folder: str,
        custom_headers: Dict[str, str],
    ) -> bool:
        """Move a message while adding custom headers.

        Fetches the original message, adds custom headers,
        recreates it in the destination folder, then deletes
        the original.

        Args:
            message_id: The ID of the message to move
            destination_folder: The destination folder
            custom_headers: Headers to add

        Returns:
            bool: True if successful
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return False

        if not destination_folder:
            self.logger.debug(
                f"No move folder for message "
                f"{message_id}, skipping"
            )
            return True

        if not custom_headers:
            self.logger.debug(
                "No custom headers, using regular move"
            )
            return self.move_to_folder(
                message_id, destination_folder
            )

        try:
            self.logger.debug(
                f"Fetching message {message_id} "
                f"for header modification"
            )
            raw_data = self.client.fetch(
                [int(message_id)],
                ['BODY.PEEK[]', 'FLAGS', 'INTERNALDATE'],
            )

            if int(message_id) not in raw_data:
                self.logger.error(
                    f"Message {message_id} not found"
                )
                return False

            msg_info = raw_data[int(message_id)]
            orig_bytes = msg_info[b'BODY[]']
            orig_flags = msg_info[b'FLAGS']
            orig_date = msg_info[b'INTERNALDATE']

            parsed = email.message_from_bytes(orig_bytes)

            for hdr_name, hdr_val in custom_headers.items():
                if hdr_name in parsed:
                    del parsed[hdr_name]
                    self.logger.debug(
                        f"Removed existing header: "
                        f"{hdr_name}"
                    )
                parsed[hdr_name] = hdr_val
                self.logger.debug(
                    f"Added header: "
                    f"{hdr_name}: {hdr_val}"
                )

            modified_bytes = parsed.as_bytes()

            if not self._ensure_folder_exists(
                destination_folder
            ):
                return False

            self.logger.debug(
                f"Appending modified message "
                f"to '{destination_folder}'"
            )
            result = self.client.append(
                destination_folder, modified_bytes,
                flags=orig_flags, msg_time=orig_date,
            )

            if result:
                self.logger.debug(
                    f"Deleting original message "
                    f"{message_id}"
                )
                self.client.delete_messages(
                    [int(message_id)]
                )
                self.client.expunge()
                self.logger.info(
                    f"Moved message {message_id} to "
                    f"'{destination_folder}' with headers"
                )
                return True
            else:
                self.logger.error(
                    f"Failed to append message "
                    f"to '{destination_folder}'"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"Error moving message {message_id} "
                f"with headers to "
                f"'{destination_folder}': {e}"
            )
            return False

    def delete_message(self, message_id: str) -> bool:
        """Delete a message.

        Args:
            message_id: The ID of the message to delete

        Returns:
            bool: True if successful
        """
        if not self.client:
            self.logger.error(
                "Not connected to IMAP server"
            )
            return False

        try:
            self.client.delete_messages([int(message_id)])
            self.client.expunge()
            self.logger.info(
                f"Deleted message {message_id}"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error deleting message "
                f"{message_id}: {e}"
            )
            return False
