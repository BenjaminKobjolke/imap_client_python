"""
Basic usage example for the IMAP Client Library
"""
import logging
from imap_client_lib import ImapClient, Account

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # Create an account configuration
    account = Account(
        name="My Email Account",
        server="imap.example.com",  # Replace with your IMAP server
        username="your.email@example.com",  # Replace with your email
        password="your_password",  # Replace with your password
        port=993,
        use_ssl=True
    )
    
    # Create the IMAP client
    client = ImapClient(account)
    
    # Connect to the server
    if not client.connect():
        print("Failed to connect to IMAP server")
        return
        
    try:
        # Get unread messages
        print("Fetching unread messages...")
        messages = client.get_unread_messages()
        
        if not messages:
            print("No unread messages found")
            return
            
        print(f"Found {len(messages)} unread messages")
        
        # Process each message
        for message_id, email_message in messages:
            print(f"\n{'='*50}")
            print(f"Message ID: {message_id}")
            print(f"From: {email_message.from_address}")
            print(f"Subject: {email_message.subject}")
            print(f"Date: {email_message.date}")
            print(f"Attachments: {len(email_message.attachments)}")
            
            # Process attachments
            if email_message.attachments:
                print("\nAttachments:")
                for i, attachment in enumerate(email_message.attachments, 1):
                    print(f"  {i}. {attachment.filename} ({attachment.content_type})")
                    
                    # Example: Save PDF attachments
                    if attachment.filename.lower().endswith('.pdf'):
                        saved_path = client.save_attachment(
                            attachment, 
                            "downloaded_attachments"  # Save to this directory
                        )
                        if saved_path:
                            print(f"     Saved to: {saved_path}")
            
            # Example: Mark specific messages as read based on criteria
            if "important" in email_message.subject.lower():
                if client.mark_as_read(message_id):
                    print("\nMarked as read (contains 'important' in subject)")
                    
            # Example: Move messages to a specific folder
            # if client.move_to_folder(message_id, "Processed"):
            #     print("Moved to 'Processed' folder")
                    
    finally:
        # Always disconnect when done
        client.disconnect()
        print("\nDisconnected from server")


if __name__ == "__main__":
    main()