"""
IMAP client for connecting to email servers and retrieving messages.
"""
from typing import List, Optional, Tuple, Callable, Dict
import os
from pathlib import Path
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import email
from email.message import Message

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
            
    def move_to_folder(self, message_id: str, folder: str, 
                      custom_headers: Optional[Dict[str, str]] = None) -> bool:
        """
        Move a message to a different folder.
        
        Args:
            message_id: The ID of the message to move
            folder: The destination folder
            custom_headers: Optional dictionary of custom headers to add during move
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client:
            self.logger.error("Not connected to IMAP server")
            return False
            
        if not folder:
            self.logger.debug(f"No move folder specified for message {message_id}, skipping move")
            return True
        
        # If custom headers are provided, use the header-aware move function
        if custom_headers:
            return self.move_with_headers(message_id, folder, custom_headers)
            
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
            
    def move_message(self, message_id: str, destination_folder: str, 
                    custom_headers: Optional[Dict[str, str]] = None) -> bool:
        """
        Move a message from current folder to another folder.
        
        Args:
            message_id: The ID of the message to move
            destination_folder: The destination folder name
            custom_headers: Optional dictionary of custom headers to add during move
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.move_to_folder(message_id, destination_folder, custom_headers)
    
    def move_with_headers(self, message_id: str, destination_folder: str, 
                         custom_headers: Dict[str, str]) -> bool:
        """
        Move a message to a different folder while adding custom headers.
        
        This function fetches the original message, adds custom headers,
        and recreates it in the destination folder before deleting the original.
        
        Args:
            message_id: The ID of the message to move
            destination_folder: The destination folder
            custom_headers: Dictionary of custom headers to add (key: value pairs)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client:
            self.logger.error("Not connected to IMAP server")
            return False
            
        if not destination_folder:
            self.logger.debug(f"No move folder specified for message {message_id}, skipping move")
            return True
            
        if not custom_headers:
            self.logger.debug("No custom headers provided, using regular move")
            return self.move_to_folder(message_id, destination_folder)
            
        try:
            # Get current folder name
            current_folder = self.client.folder_status('INBOX')[b'UIDNEXT']  # This is just to ensure we're in a folder
            
            # Fetch the original message
            self.logger.debug(f"Fetching message {message_id} for header modification")
            raw_message_data = self.client.fetch([int(message_id)], ['BODY.PEEK[]', 'FLAGS', 'INTERNALDATE'])
            
            if int(message_id) not in raw_message_data:
                self.logger.error(f"Message {message_id} not found")
                return False
                
            message_info = raw_message_data[int(message_id)]
            original_message_bytes = message_info[b'BODY[]']
            original_flags = message_info[b'FLAGS']
            original_date = message_info[b'INTERNALDATE']
            
            # Parse the email message
            parsed_message = email.message_from_bytes(original_message_bytes)
            
            # Add custom headers
            for header_name, header_value in custom_headers.items():
                # Remove existing header if it exists to prevent duplicates
                if header_name in parsed_message:
                    del parsed_message[header_name]
                    self.logger.debug(f"Removed existing header: {header_name}")
                
                parsed_message[header_name] = header_value
                self.logger.debug(f"Added custom header: {header_name}: {header_value}")
            
            # Convert back to bytes
            modified_message_bytes = parsed_message.as_bytes()
            
            # Check if destination folder exists
            folders = self.client.list_folders()
            folder_names = [f[2] for f in folders]
            
            if destination_folder not in folder_names:
                self.logger.warning(f"Folder '{destination_folder}' does not exist, attempting to create it")
                try:
                    self.client.create_folder(destination_folder)
                    self.logger.info(f"Created folder '{destination_folder}'")
                except Exception as e:
                    self.logger.error(f"Error creating folder '{destination_folder}': {e}")
                    return False
            
            # Append the modified message to destination folder
            self.logger.debug(f"Appending modified message to folder '{destination_folder}'")
            append_result = self.client.append(destination_folder, modified_message_bytes, 
                                             flags=original_flags, msg_time=original_date)
            
            if append_result:
                # Delete the original message
                self.logger.debug(f"Deleting original message {message_id}")
                self.client.delete_messages([int(message_id)])
                self.client.expunge()
                
                self.logger.info(f"Successfully moved message {message_id} to folder '{destination_folder}' with custom headers")
                return True
            else:
                self.logger.error(f"Failed to append modified message to folder '{destination_folder}'")
                return False
                
        except Exception as e:
            self.logger.error(f"Error moving message {message_id} with headers to folder '{destination_folder}': {e}")
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
            
    def forward_email(self, email_message: EmailMessage, to_addresses: List[str], 
                     new_subject: Optional[str] = None, smtp_server: Optional[str] = None, 
                     smtp_port: int = 587, smtp_username: Optional[str] = None, 
                     smtp_password: Optional[str] = None, sender_email: Optional[str] = None,
                     bcc_addresses: Optional[List[str]] = None, custom_headers: Optional[Dict[str, str]] = None,
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
            bcc_addresses: List of email addresses to BCC (blind carbon copy)
            custom_headers: Dictionary of custom headers to add to the forwarded email
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
            
            # Check if we have inline images to determine message structure
            has_inline_images = any(att.is_inline and att.content_id for att in email_message.attachments)
            
            # Create multipart message - use 'related' if we have inline images
            if has_inline_images:
                msg = MIMEMultipart('related')
            else:
                msg = MIMEMultipart()
                
            msg['From'] = sender_email
            msg['To'] = ', '.join(to_addresses)
            if bcc_addresses:
                msg['Bcc'] = ', '.join(bcc_addresses)
            msg['Subject'] = new_subject
            
            # Add custom headers if provided
            if custom_headers:
                for header_name, header_value in custom_headers.items():
                    # Remove existing header if it exists to prevent duplicates
                    if header_name in msg:
                        del msg[header_name]
                        self.logger.debug(f"Removed existing header: {header_name}")
                    
                    msg[header_name] = header_value
                    self.logger.debug(f"Added custom header: {header_name}: {header_value}")
            
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
            
            # If we have both text and HTML with inline images, create alternative structure
            if has_inline_images and original_body_html:
                # Create a multipart/alternative container for text and HTML versions
                alternative = MIMEMultipart('alternative')
                
                # Add text content
                if additional_message:
                    forward_content = f"{additional_message}\n\n{forward_header}{original_body_text}"
                else:
                    forward_content = f"{forward_header}{original_body_text}"
                alternative.attach(MIMEText(forward_content, 'plain'))
                
                # Add HTML content
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
                alternative.attach(MIMEText(html_content, 'html'))
                
                # Attach the alternative part to the main message
                msg.attach(alternative)
            else:
                # Simple structure for emails without inline images
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
                    
                    # Ensure Content-ID is properly formatted with angle brackets
                    content_id = attachment.content_id
                    if not content_id.startswith('<'):
                        content_id = f'<{content_id}>'
                    if not content_id.endswith('>'):
                        content_id = f'{content_id[:-1]}>' if content_id.endswith('>') else f'{content_id}>'
                    
                    part.add_header('Content-ID', content_id)
                    msg.attach(part)
                    self.logger.debug(f"Attached inline image: {attachment.filename} with Content-ID: {content_id}")
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
                
                # Prepare all recipients (TO + BCC)
                all_recipients = to_addresses.copy()
                if bcc_addresses:
                    all_recipients.extend(bcc_addresses)
                
                # Send to all recipients
                server.send_message(msg, to_addrs=all_recipients)
                
            # Log successful forwarding
            log_message = f"Successfully forwarded email to: {', '.join(to_addresses)}"
            if bcc_addresses:
                log_message += f" (BCC: {', '.join(bcc_addresses)})"
            self.logger.info(log_message)
            return True
            
        except Exception as e:
            self.logger.error(f"Error forwarding email: {e}")
            return False
    
    def save_draft(self, to_addresses: List[str], subject: str, body: str,
                   from_email: Optional[str] = None, cc_addresses: Optional[List[str]] = None,
                   bcc_addresses: Optional[List[str]] = None, custom_headers: Optional[Dict[str, str]] = None,
                   content_type: str = "text/plain", attachments: Optional[List[Attachment]] = None,
                   draft_folder: str = "Drafts") -> bool:
        """
        Save a draft email to the drafts folder.
        
        Args:
            to_addresses: List of recipient email addresses
            subject: Email subject line
            body: Email body content
            from_email: Sender email address (if None, uses account username)
            cc_addresses: List of CC email addresses
            bcc_addresses: List of BCC email addresses
            custom_headers: Dictionary of custom headers to add
            content_type: Content type ("text/plain" or "text/html")
            attachments: List of Attachment objects to include
            draft_folder: Name of the drafts folder (default: "Drafts")
            
        Returns:
            bool: True if draft was saved successfully, False otherwise
        """
        if not self.client:
            self.logger.error("Not connected to IMAP server")
            return False
            
        try:
            # Use account username if from_email not provided
            if from_email is None:
                from_email = self.account.username
            
            # Check if we have attachments to determine message structure
            has_attachments = attachments and len(attachments) > 0
            has_inline_images = has_attachments and any(att.is_inline and att.content_id for att in attachments)
            
            # Create multipart message - use 'related' if we have inline images
            if has_inline_images:
                msg = MIMEMultipart('related')
            elif has_attachments:
                msg = MIMEMultipart('mixed')
            else:
                msg = MIMEMultipart()
            
            # Set standard headers
            msg['From'] = from_email
            msg['To'] = ', '.join(to_addresses)
            if cc_addresses:
                msg['Cc'] = ', '.join(cc_addresses)
            if bcc_addresses:
                msg['Bcc'] = ', '.join(bcc_addresses)
            msg['Subject'] = subject
            
            # Add custom headers if provided
            if custom_headers:
                for header_name, header_value in custom_headers.items():
                    # Remove existing header if it exists to prevent duplicates
                    if header_name in msg:
                        del msg[header_name]
                        self.logger.debug(f"Removed existing header: {header_name}")
                    
                    msg[header_name] = header_value
                    self.logger.debug(f"Added custom header: {header_name}: {header_value}")
            
            # Add email content
            if has_inline_images and content_type == "text/html":
                # Create a multipart/alternative container for text and HTML versions
                alternative = MIMEMultipart('alternative')
                
                # Add plain text version (simplified from HTML if needed)
                alternative.attach(MIMEText(body, 'plain'))
                alternative.attach(MIMEText(body, 'html'))
                
                # Attach the alternative part to the main message
                msg.attach(alternative)
            else:
                # Simple content
                msg.attach(MIMEText(body, content_type.split('/')[-1]))
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    if attachment.is_inline and attachment.content_id:
                        # Handle inline images
                        main_type, sub_type = attachment.content_type.split('/', 1)
                        part = MIMEBase(main_type, sub_type)
                        part.set_payload(attachment.data)
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', 'inline', filename=attachment.filename)
                        
                        # Ensure Content-ID is properly formatted with angle brackets
                        content_id = attachment.content_id
                        if not content_id.startswith('<'):
                            content_id = f'<{content_id}>'
                        if not content_id.endswith('>'):
                            content_id = f'{content_id[:-1]}>' if content_id.endswith('>') else f'{content_id}>'
                        
                        part.add_header('Content-ID', content_id)
                        msg.attach(part)
                        self.logger.debug(f"Attached inline image: {attachment.filename} with Content-ID: {content_id}")
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
            
            # Check if draft folder exists
            folders = self.client.list_folders()
            folder_names = [f[2] for f in folders]
            
            if draft_folder not in folder_names:
                self.logger.warning(f"Draft folder '{draft_folder}' does not exist, attempting to create it")
                try:
                    self.client.create_folder(draft_folder)
                    self.logger.info(f"Created draft folder '{draft_folder}'")
                except Exception as e:
                    self.logger.error(f"Error creating draft folder '{draft_folder}': {e}")
                    return False
            
            # Convert message to bytes
            message_bytes = msg.as_bytes()
            
            # Append draft to folder with \Draft flag
            self.logger.debug(f"Saving draft to folder '{draft_folder}'")
            append_result = self.client.append(draft_folder, message_bytes, flags=[b'\\Draft'])
            
            if append_result:
                self.logger.info(f"Successfully saved draft to folder '{draft_folder}'")
                return True
            else:
                self.logger.error(f"Failed to save draft to folder '{draft_folder}'")
                return False
                
        except Exception as e:
            self.logger.error(f"Error saving draft: {e}")
            return False
    
    def update_draft(self, message_id: str, to_addresses: List[str], subject: str, body: str,
                    from_email: Optional[str] = None, cc_addresses: Optional[List[str]] = None,
                    bcc_addresses: Optional[List[str]] = None, custom_headers: Optional[Dict[str, str]] = None,
                    content_type: str = "text/plain", attachments: Optional[List[Attachment]] = None,
                    draft_folder: str = "Drafts") -> bool:
        """
        Update an existing draft email by replacing it with new content.
        
        This method deletes the existing draft and creates a new one with updated content.
        
        Args:
            message_id: The ID of the existing draft message to update
            to_addresses: List of recipient email addresses
            subject: Email subject line
            body: Email body content
            from_email: Sender email address (if None, uses account username)
            cc_addresses: List of CC email addresses
            bcc_addresses: List of BCC email addresses
            custom_headers: Dictionary of custom headers to add
            content_type: Content type ("text/plain" or "text/html")
            attachments: List of Attachment objects to include
            draft_folder: Name of the drafts folder (default: "Drafts")
            
        Returns:
            bool: True if draft was updated successfully, False otherwise
        """
        if not self.client:
            self.logger.error("Not connected to IMAP server")
            return False
            
        try:
            # First, verify the message exists and is in the draft folder
            self.client.select_folder(draft_folder)
            
            # Check if the message exists
            try:
                message_data = self.client.fetch([int(message_id)], ['FLAGS'])
                if int(message_id) not in message_data:
                    self.logger.error(f"Draft message {message_id} not found in folder '{draft_folder}'")
                    return False
                    
                # Verify it's actually a draft (has \Draft flag)
                flags = message_data[int(message_id)][b'FLAGS']
                if b'\\Draft' not in flags:
                    self.logger.warning(f"Message {message_id} does not have \\Draft flag. Proceeding anyway.")
                    
            except Exception as e:
                self.logger.error(f"Error checking draft message {message_id}: {e}")
                return False
            
            # Save the new draft content
            self.logger.debug(f"Creating updated draft content for message {message_id}")
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
                draft_folder=draft_folder
            )
            
            if not draft_saved:
                self.logger.error("Failed to save updated draft content")
                return False
            
            # Delete the old draft
            self.logger.debug(f"Deleting old draft message {message_id}")
            try:
                self.client.delete_messages([int(message_id)])
                self.client.expunge()
                self.logger.info(f"Successfully updated draft (deleted old message {message_id})")
                return True
            except Exception as e:
                self.logger.error(f"Error deleting old draft message {message_id}: {e}")
                # The new draft was saved, but we couldn't delete the old one
                self.logger.warning("Updated draft was saved, but old draft could not be deleted")
                return True  # Still consider this a success since new draft exists
                
        except Exception as e:
            self.logger.error(f"Error updating draft: {e}")
            return False