"""
Example showing how to extend the Account class for application-specific needs
"""
from dataclasses import dataclass
from typing import Optional
from imap_client_lib import Account, ImapClient


@dataclass
class FileMovingAccount(Account):
    """
    Extended Account class for the file moving application.
    Adds application-specific fields while inheriting IMAP configuration.
    """
    target_folder: Optional[str] = None
    imap_move_folder: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FileMovingAccount':
        """
        Create a FileMovingAccount instance from a dictionary.
        
        Args:
            data: Dictionary containing account configuration
            
        Returns:
            FileMovingAccount: New FileMovingAccount instance
        """
        return cls(
            # Base Account fields
            name=data.get('name', ''),
            server=data.get('server', ''),
            username=data.get('username', ''),
            password=data.get('password', ''),
            port=data.get('port', 993),
            use_ssl=data.get('use_ssl', True),
            # Application-specific fields
            target_folder=data.get('target_folder'),
            imap_move_folder=data.get('imap_move_folder')
        )


def main():
    """
    Example usage of the extended account class
    """
    # Load configuration (this could come from a JSON file)
    config = {
        "name": "Work Email",
        "server": "imap.company.com",
        "username": "user@company.com",
        "password": "secure_password",
        "port": 993,
        "use_ssl": True,
        "target_folder": "/home/user/email_attachments",
        "imap_move_folder": "Processed"
    }
    
    # Create extended account instance
    account = FileMovingAccount.from_dict(config)
    
    # The ImapClient works with the extended account seamlessly
    # because FileMovingAccount is still an Account
    client = ImapClient(account)
    
    if client.connect():
        try:
            # Get unread messages
            messages = client.get_unread_messages()
            
            for message_id, email_message in messages:
                print(f"Processing: {email_message.subject}")
                
                # Process attachments and save to target folder
                for attachment in email_message.attachments:
                    # Use the extended account's target_folder
                    if account.target_folder:
                        saved_path = client.save_attachment(
                            attachment, 
                            account.target_folder
                        )
                        if saved_path:
                            print(f"  Saved: {saved_path}")
                
                # Mark as read
                client.mark_as_read(message_id)
                
                # Move to folder using extended account's imap_move_folder
                if account.imap_move_folder:
                    client.move_to_folder(message_id, account.imap_move_folder)
                    
        finally:
            client.disconnect()
    
    # You can also create a custom client that uses these fields
    class FileMovingImapClient(ImapClient):
        """Extended IMAP client that uses FileMovingAccount features"""
        
        def process_and_save_attachments(self, message_id: str, 
                                       email_message: EmailMessage) -> int:
            """
            Process message and save attachments to configured target folder.
            
            Returns number of attachments saved.
            """
            if not isinstance(self.account, FileMovingAccount):
                raise ValueError("This method requires a FileMovingAccount")
                
            saved_count = 0
            
            # Save attachments to target folder
            if self.account.target_folder:
                for attachment in email_message.attachments:
                    saved_path = self.save_attachment(
                        attachment,
                        self.account.target_folder
                    )
                    if saved_path:
                        saved_count += 1
                        
            # Mark as read and move if configured
            self.mark_as_read(message_id)
            
            if self.account.imap_move_folder:
                self.move_to_folder(message_id, self.account.imap_move_folder)
                
            return saved_count


if __name__ == "__main__":
    main()