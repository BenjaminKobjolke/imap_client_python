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


class ImapClient:
    """
    Handles IMAP connections and email operations.
    """
    
    def __init__(self, account: Account, logger: Optional[logging.Logger] = None):
        """
        Initialize the IMAP client with an account.
        
        Args:
            account: The email account configuration
            logger: Optional logger instance
        """
        self.account = account
        self.client = None
        self.logger = logger or logging.getLogger(__name__)
        
    def connect(self) -> bool:
        """
        Connect to the IMAP server.
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        try:
            self.logger.info(f"Connecting to {self.account.server} for account {self.account.name}")
            self.client = IMAPClient(
                self.account.server, 
                port=self.account.port, 
                use_uid=True, 
                ssl=self.account.use_ssl
            )
            self.client.login(self.account.username, self.account.password)
            self.logger.info(f"Successfully connected to {self.account.server}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.account.server}: {e}")
            return False
            
    def disconnect(self):
        """
        Disconnect from the IMAP server.
        """
        if self.client:
            try:
                self.client.logout()
                self.logger.info(f"Disconnected from {self.account.server}")
            except Exception as e:
                self.logger.error(f"Error disconnecting from {self.account.server}: {e}")
            finally:
                self.client = None
                
    def get_messages(self, search_criteria: List[str] = None, folder: str = 'INBOX') -> List[Tuple[str, EmailMessage]]:
        """
        Get messages from a folder based on search criteria.
        
        Args:
            search_criteria: IMAP search criteria (default: ['UNSEEN'] for unread messages)
            folder: The folder to search in (default: 'INBOX')
            
        Returns:
            List[Tuple[str, EmailMessage]]: List of message IDs and parsed email messages
        """
        if not self.client:
            self.logger.error("Not connected to IMAP server")
            return []
            
        if search_criteria is None:
            search_criteria = ['UNSEEN']
            
        try:
            # Select the folder
            self.client.select_folder(folder)
            
            # Search for messages
            self.logger.info(f"Searching for messages with criteria: {search_criteria}")
            message_ids = self.client.search(search_criteria)
            
            if not message_ids:
                self.logger.info("No messages found")
                return []
                
            self.logger.info(f"Found {len(message_ids)} messages")
            
            # Fetch message data
            messages = []
            for message_id in message_ids:
                try:
                    raw_message = self.client.fetch([message_id], ['BODY.PEEK[]'])
                    message_data = raw_message[message_id][b'BODY[]']
                    email_message = EmailMessage.from_bytes(str(message_id), message_data, self.logger)
                    messages.append((str(message_id), email_message))
                except Exception as e:
                    self.logger.error(f"Error fetching message {message_id}: {e}")
                    
            return messages
        except Exception as e:
            self.logger.error(f"Error getting messages: {e}")
            return []
            
    def get_unread_messages(self) -> List[Tuple[str, EmailMessage]]:
        """
        Get all unread messages from the inbox.
        
        Returns:
            List[Tuple[str, EmailMessage]]: List of message IDs and parsed email messages
        """
        return self.get_messages(['UNSEEN'], 'INBOX')
            
    def mark_as_read(self, message_id: str) -> bool:
        """
        Mark a message as read.
        
        Args:
            message_id: The ID of the message to mark as read
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client:
            self.logger.error("Not connected to IMAP server")
            return False
            
        try:
            self.client.add_flags([int(message_id)], [b'\\Seen'])
            self.logger.info(f"Marked message {message_id} as read")
            return True
        except Exception as e:
            self.logger.error(f"Error marking message {message_id} as read: {e}")
            return False
            
    def mark_as_unread(self, message_id: str) -> bool:
        """
        Mark a message as unread.
        
        Args:
            message_id: The ID of the message to mark as unread
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client:
            self.logger.error("Not connected to IMAP server")
            return False
            
        try:
            self.client.remove_flags([int(message_id)], [b'\\Seen'])
            self.logger.info(f"Marked message {message_id} as unread")
            return True
        except Exception as e:
            self.logger.error(f"Error marking message {message_id} as unread: {e}")
            return False
            
    def move_to_folder(self, message_id: str, folder: str) -> bool:
        """
        Move a message to a different folder.
        
        Args:
            message_id: The ID of the message to move
            folder: The destination folder
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client:
            self.logger.error("Not connected to IMAP server")
            return False
            
        if not folder:
            self.logger.debug(f"No move folder specified for message {message_id}, skipping move")
            return True
            
        try:
            # Check if folder exists
            folders = self.client.list_folders()
            folder_names = [f[2] for f in folders]
            
            if folder not in folder_names:
                self.logger.warning(f"Folder '{folder}' does not exist, attempting to create it")
                try:
                    self.client.create_folder(folder)
                    self.logger.info(f"Created folder '{folder}'")
                except Exception as e:
                    self.logger.error(f"Error creating folder '{folder}': {e}")
                    return False
            
            # Move the message
            self.client.move([int(message_id)], folder)
            self.logger.info(f"Moved message {message_id} to folder '{folder}'")
            return True
        except Exception as e:
            self.logger.error(f"Error moving message {message_id} to folder '{folder}': {e}")
            return False
            
    def delete_message(self, message_id: str) -> bool:
        """
        Delete a message.
        
        Args:
            message_id: The ID of the message to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client:
            self.logger.error("Not connected to IMAP server")
            return False
            
        try:
            self.client.delete_messages([int(message_id)])
            self.logger.info(f"Deleted message {message_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting message {message_id}: {e}")
            return False
            
    def list_folders(self) -> List[str]:
        """
        List all folders in the mailbox.
        
        Returns:
            List[str]: List of folder names
        """
        if not self.client:
            self.logger.error("Not connected to IMAP server")
            return []
            
        try:
            folders = self.client.list_folders()
            folder_names = [f[2] for f in folders]
            return folder_names
        except Exception as e:
            self.logger.error(f"Error listing folders: {e}")
            return []
            
    def save_attachment(self, attachment: Attachment, target_path: str, 
                       sanitize_filename: bool = True) -> str:
        """
        Save an attachment to disk.
        
        Args:
            attachment: The attachment to save
            target_path: The directory to save to or full file path
            sanitize_filename: Whether to sanitize the filename
            
        Returns:
            str: The full path where the file was saved, or empty string on error
        """
        try:
            # Determine if target_path is a directory or file
            if os.path.isdir(target_path) or not os.path.splitext(target_path)[1]:
                # It's a directory
                target_dir = Path(target_path)
                os.makedirs(target_dir, exist_ok=True)
                
                # Sanitize filename if requested
                filename = attachment.filename
                if sanitize_filename:
                    filename = filename.replace('/', '_').replace('\\', '_')
                    self.logger.debug(f"Sanitized filename: '{attachment.filename}' -> '{filename}'")
                
                file_path = target_dir / filename
            else:
                # It's a full file path
                file_path = Path(target_path)
                os.makedirs(file_path.parent, exist_ok=True)
            
            # Handle duplicate filenames
            counter = 1
            original_path = file_path
            while file_path.exists():
                name = original_path.stem
                ext = original_path.suffix
                file_path = original_path.parent / f"{name}_{counter}{ext}"
                counter += 1
                
            # Write the file
            with open(file_path, 'wb') as f:
                f.write(attachment.data)
                
            self.logger.info(f"Saved attachment to {file_path}")
            return str(file_path)
            
        except Exception as e:
            self.logger.error(f"Error saving attachment {attachment.filename}: {e}")
            return ""
            
    def process_messages_with_callback(self, callback: Callable[[EmailMessage], bool],
                                     search_criteria: List[str] = None,
                                     folder: str = 'INBOX',
                                     mark_as_read: bool = True,
                                     move_to_folder: Optional[str] = None) -> int:
        """
        Process messages with a custom callback function.
        
        Args:
            callback: Function that takes an EmailMessage and returns True to continue processing
            search_criteria: IMAP search criteria (default: ['UNSEEN'])
            folder: The folder to search in (default: 'INBOX')
            mark_as_read: Whether to mark processed messages as read
            move_to_folder: Optional folder to move processed messages to
            
        Returns:
            int: Number of messages processed
        """
        if not self.connect():
            return 0
            
        try:
            messages = self.get_messages(search_criteria, folder)
            processed_count = 0
            
            for message_id, email_message in messages:
                try:
                    # Call the callback
                    if callback(email_message):
                        processed_count += 1
                        
                        # Mark as read if requested
                        if mark_as_read:
                            self.mark_as_read(message_id)
                            
                        # Move to folder if requested
                        if move_to_folder:
                            self.move_to_folder(message_id, move_to_folder)
                            
                except Exception as e:
                    self.logger.error(f"Error processing message {message_id}: {e}")
                    
            return processed_count
            
        finally:
            self.disconnect()