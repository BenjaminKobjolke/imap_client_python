"""
IMAP client for connecting to email servers and retrieving messages.
"""
from typing import List, Optional, Tuple, Callable
import os
from pathlib import Path
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

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
        
    def get_all_messages(self, folder: str = 'INBOX') -> List[Tuple[str, EmailMessage]]:
        """
        Get all messages from a specific folder.
        
        Args:
            folder: The folder to get messages from (default: 'INBOX')
            
        Returns:
            List[Tuple[str, EmailMessage]]: List of message IDs and parsed email messages
        """
        return self.get_messages(['ALL'], folder)
            
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
            
    def move_message(self, message_id: str, destination_folder: str) -> bool:
        """
        Move a message from current folder to another folder.
        
        Args:
            message_id: The ID of the message to move
            destination_folder: The destination folder name
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.move_to_folder(message_id, destination_folder)
            
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
            
    def forward_email(self, email_message: EmailMessage, to_addresses: List[str], 
                     new_subject: Optional[str] = None, smtp_server: Optional[str] = None, 
                     smtp_port: int = 587, smtp_username: Optional[str] = None, 
                     smtp_password: Optional[str] = None, sender_email: Optional[str] = None,
                     additional_message: str = "") -> bool:
        """
        Forward an email with an optional modified subject.
        
        Args:
            email_message: The EmailMessage to forward
            to_addresses: List of email addresses to forward to
            new_subject: New subject line (if None, uses "Fwd: " + original subject)
            smtp_server: SMTP server to use (if None, attempts to derive from account)
            smtp_port: SMTP port (default: 587)
            smtp_username: SMTP username (if None, uses account username)
            smtp_password: SMTP password (if None, uses account password)
            sender_email: Fully-qualified sender email address (if None, uses smtp_username)
            additional_message: Additional message to prepend to the forwarded email
            
        Returns:
            bool: True if forwarding was successful, False otherwise
        """
        try:
            # Prepare subject
            if new_subject is None:
                new_subject = f"Fwd: {email_message.subject}"
            
            # Use account credentials if SMTP credentials not provided
            if smtp_username is None:
                smtp_username = self.account.username
            if smtp_password is None:
                smtp_password = self.account.password
                
            # Use sender_email if provided, otherwise use smtp_username
            if sender_email is None:
                sender_email = smtp_username
                
            # Try to derive SMTP server from IMAP server if not provided
            if smtp_server is None:
                smtp_server = self.account.server.replace('imap', 'smtp')
                self.logger.info(f"Derived SMTP server: {smtp_server}")
            
            # Create multipart message
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = ', '.join(to_addresses)
            msg['Subject'] = new_subject
            
            # Get original email body
            original_body_text = email_message.get_body('text/plain') or ""
            original_body_html = email_message.get_body('text/html') or ""
            
            # Create forwarded message content
            forward_header = f"""
---------- Forwarded message ----------
From: {email_message.from_address}
Date: {email_message.date}
Subject: {email_message.subject}

"""
            
            # Combine additional message with forwarded content
            if additional_message:
                forward_content = f"{additional_message}\n\n{forward_header}{original_body_text}"
            else:
                forward_content = f"{forward_header}{original_body_text}"
            
            # Add text content
            msg.attach(MIMEText(forward_content, 'plain'))
            
            # Add HTML content if available
            if original_body_html:
                html_content = f"""
                <p>{additional_message.replace(chr(10), '<br>')}</p>
                <div>
                <p>---------- Forwarded message ----------<br>
                From: {email_message.from_address}<br>
                Date: {email_message.date}<br>
                Subject: {email_message.subject}</p>
                <div>{original_body_html}</div>
                </div>
                """ if additional_message else f"""
                <div>
                <p>---------- Forwarded message ----------<br>
                From: {email_message.from_address}<br>
                Date: {email_message.date}<br>
                Subject: {email_message.subject}</p>
                <div>{original_body_html}</div>
                </div>
                """
                msg.attach(MIMEText(html_content, 'html'))
            
            # Forward attachments and inline images
            for attachment in email_message.attachments:
                if attachment.is_inline and attachment.content_id:
                    # Handle inline images
                    main_type, sub_type = attachment.content_type.split('/', 1)
                    part = MIMEBase(main_type, sub_type)
                    part.set_payload(attachment.data)
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', 'inline', filename=attachment.filename)
                    part.add_header('Content-ID', attachment.content_id)
                    msg.attach(part)
                    self.logger.debug(f"Attached inline image: {attachment.filename} with Content-ID: {attachment.content_id}")
                else:
                    # Handle regular attachments
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.data)
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment.filename}'
                    )
                    msg.attach(part)
                    self.logger.debug(f"Attached file: {attachment.filename}")
            
            # Send email via SMTP
            self.logger.info(f"Connecting to SMTP server: {smtp_server}:{smtp_port}")
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
                
            self.logger.info(f"Successfully forwarded email to: {', '.join(to_addresses)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error forwarding email: {e}")
            return False