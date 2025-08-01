"""
Email message model for representing email data.
"""
from dataclasses import dataclass
from typing import List, Optional
import email
from email.message import Message
import email.header
import logging


@dataclass
class Attachment:
    """
    Represents an email attachment.
    """
    filename: str
    content_type: str
    data: bytes
    content_id: Optional[str] = None
    is_inline: bool = False


@dataclass
class EmailMessage:
    """
    Represents an email message with its metadata and attachments.
    """
    message_id: str
    from_address: str
    subject: str
    date: str
    attachments: List[Attachment]
    raw_message: Message

    def get_body(self, content_type: str = "text/plain") -> Optional[str]:
        """
        Extract the email body content.
        
        Args:
            content_type: The content type to extract ('text/plain' or 'text/html')
            
        Returns:
            str: The email body content or None if not found
        """
        if self.raw_message.is_multipart():
            for part in self.raw_message.walk():
                if part.get_content_type() == content_type:
                    payload = part.get_payload(decode=True)
                    if payload:
                        try:
                            # Try to decode with the charset specified in the message
                            charset = part.get_content_charset() or 'utf-8'
                            return payload.decode(charset)
                        except (UnicodeDecodeError, LookupError):
                            # Fallback to utf-8 if charset fails
                            try:
                                return payload.decode('utf-8')
                            except UnicodeDecodeError:
                                # Last resort: decode with errors='replace'
                                return payload.decode('utf-8', errors='replace')
        else:
            if self.raw_message.get_content_type() == content_type:
                payload = self.raw_message.get_payload(decode=True)
                if payload:
                    try:
                        charset = self.raw_message.get_content_charset() or 'utf-8'
                        return payload.decode(charset)
                    except (UnicodeDecodeError, LookupError):
                        try:
                            return payload.decode('utf-8')
                        except UnicodeDecodeError:
                            return payload.decode('utf-8', errors='replace')
        return None

    @classmethod
    def from_bytes(cls, message_id: str, message_data: bytes, logger: Optional[logging.Logger] = None, 
                   include_attachments: bool = True) -> 'EmailMessage':
        """
        Create an EmailMessage instance from raw message bytes.
        
        Args:
            message_id: The unique ID of the message
            message_data: The raw message data
            logger: Optional logger for debug information
            include_attachments: Whether to process and include attachments (default: True)
            
        Returns:
            EmailMessage: New EmailMessage instance
        """
        if logger:
            logger.debug(f"Parsing email message ID: {message_id}")
            
        # Parse the email message
        msg = email.message_from_bytes(message_data)
        
        # Extract basic headers
        from_address = msg.get('From', '')
        subject = msg.get('Subject', '')
        date = msg.get('Date', '')
        
        # Decode headers if needed
        if from_address:
            try:
                decoded_from = str(email.header.make_header(email.header.decode_header(from_address)))
                if logger and decoded_from != from_address:
                    logger.debug(f"Decoded From header: '{from_address}' -> '{decoded_from}'")
                from_address = decoded_from
            except Exception as e:
                if logger:
                    logger.debug(f"Error decoding From header: {e}")
        
        if subject:
            try:
                decoded_subject = str(email.header.make_header(email.header.decode_header(subject)))
                if logger and decoded_subject != subject:
                    logger.debug(f"Decoded Subject header: '{subject}' -> '{decoded_subject}'")
                subject = decoded_subject
            except Exception as e:
                if logger:
                    logger.debug(f"Error decoding Subject header: {e}")
        
        if logger:
            logger.debug(f"Parsed headers - From: '{from_address}', Subject: '{subject}', Date: '{date}'")
        
        # Extract attachments (only if requested)
        attachments = []
        
        if include_attachments:
            if logger:
                logger.debug("Scanning for attachments...")
                
            for part in msg.walk():
                content_disposition = part.get_content_disposition()
                content_type = part.get_content_type()
                content_id = part.get('Content-ID')
                
                if logger:
                    logger.debug(f"Message part - Content-Type: '{content_type}', Content-Disposition: '{content_disposition}', Content-ID: '{content_id}'")
                    
                filename = part.get_filename()
                
                # Handle regular attachments
                if content_disposition == 'attachment' and filename:
                    if logger:
                        logger.debug(f"Found attachment - Filename: '{filename}', Content-Type: '{content_type}'")
                        
                    data = part.get_payload(decode=True)
                    
                    if data:
                        if logger:
                            logger.debug(f"Attachment data size: {len(data)} bytes")
                            
                        attachment = Attachment(
                            filename=filename,
                            content_type=content_type,
                            data=data,
                            content_id=content_id,
                            is_inline=False
                        )
                        attachments.append(attachment)
                    else:
                        if logger:
                            logger.debug("Attachment has no data, skipping")
                
                # Handle inline images
                elif content_disposition == 'inline' or (content_id and content_type.startswith('image/')):
                    if logger:
                        logger.debug(f"Found inline image - Content-Type: '{content_type}', Content-ID: '{content_id}'")
                    
                    data = part.get_payload(decode=True)
                    
                    if data:
                        # Generate filename if not provided
                        if not filename:
                            extension = content_type.split('/')[-1] if '/' in content_type else 'bin'
                            filename = f"inline_image.{extension}"
                        
                        if logger:
                            logger.debug(f"Inline image data size: {len(data)} bytes, filename: '{filename}'")
                        
                        attachment = Attachment(
                            filename=filename,
                            content_type=content_type,
                            data=data,
                            content_id=content_id,
                            is_inline=True
                        )
                        attachments.append(attachment)
                    else:
                        if logger:
                            logger.debug("Inline image has no data, skipping")
                
                elif filename and not content_disposition:
                    # Some emails don't set content_disposition but still have attachments
                    if logger:
                        logger.debug(f"Potential attachment without Content-Disposition - Filename: '{filename}', Content-Type: '{content_type}'")
                    
                    # Try to extract it anyway
                    data = part.get_payload(decode=True)
                    
                    if data:
                        if logger:
                            logger.debug(f"Extracted attachment without Content-Disposition - Size: {len(data)} bytes")
                            
                        attachment = Attachment(
                            filename=filename,
                            content_type=content_type,
                            data=data,
                            content_id=content_id,
                            is_inline=False
                        )
                        attachments.append(attachment)
        else:
            if logger:
                logger.debug("Skipping attachment processing as requested")
        
        return cls(
            message_id=message_id,
            from_address=from_address,
            subject=subject,
            date=date,
            attachments=attachments,
            raw_message=msg
        )