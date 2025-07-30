"""
Advanced usage example for the IMAP Client Library
"""
import logging
from datetime import datetime
from imap_client_lib import ImapClient, Account, EmailMessage

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def invoice_processor(email_message: EmailMessage) -> bool:
    """
    Process emails containing invoices.
    
    Returns True if the email was processed, False otherwise.
    """
    # Check if email might contain an invoice
    keywords = ['invoice', 'bill', 'payment', 'receipt']
    subject_lower = email_message.subject.lower()
    
    if not any(keyword in subject_lower for keyword in keywords):
        return False
        
    print(f"\nProcessing potential invoice from: {email_message.from_address}")
    
    # Process PDF attachments
    pdf_found = False
    for attachment in email_message.attachments:
        if attachment.filename.lower().endswith('.pdf'):
            pdf_found = True
            print(f"  Found invoice PDF: {attachment.filename}")
            # Here you could save the PDF, extract data, etc.
            
    return pdf_found


def report_processor(email_message: EmailMessage) -> bool:
    """
    Process emails containing reports.
    """
    if 'report' not in email_message.subject.lower():
        return False
        
    print(f"\nProcessing report from: {email_message.from_address}")
    
    # Process Excel/CSV attachments
    processed = False
    for attachment in email_message.attachments:
        if attachment.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
            processed = True
            print(f"  Found report file: {attachment.filename}")
            # Here you could save and process the report
            
    return processed


def main():
    # Create account from environment variables or config file
    account = Account(
        name="Business Email",
        server="imap.example.com",
        username="business@example.com",
        password="secure_password",
        port=993,
        use_ssl=True
    )
    
    # Create client with custom logger
    logger = logging.getLogger('imap_processor')
    client = ImapClient(account, logger=logger)
    
    if not client.connect():
        print("Failed to connect to IMAP server")
        return
        
    try:
        # Example 1: List all folders
        print("Available folders:")
        folders = client.list_folders()
        for folder in folders:
            print(f"  - {folder}")
        print()
        
        # Example 2: Search for specific messages
        print("Searching for messages from the last 7 days...")
        # Note: IMAP search doesn't support relative dates directly
        # You would need to use SINCE with a specific date
        from_date = datetime(2024, 1, 1)  # Adjust as needed
        messages = client.get_messages(
            ['SINCE', from_date.strftime('%d-%b-%Y')],
            'INBOX'
        )
        print(f"Found {len(messages)} messages since {from_date}")
        
        # Example 3: Process invoices with callback
        print("\nProcessing invoices...")
        invoice_count = client.process_messages_with_callback(
            callback=invoice_processor,
            search_criteria=['SUBJECT', 'invoice', 'UNSEEN'],
            mark_as_read=True,
            move_to_folder='Invoices'
        )
        print(f"Processed {invoice_count} invoices")
        
        # Example 4: Process reports with callback  
        print("\nProcessing reports...")
        report_count = client.process_messages_with_callback(
            callback=report_processor,
            search_criteria=['SUBJECT', 'report', 'UNSEEN'],
            mark_as_read=True,
            move_to_folder='Reports'
        )
        print(f"Processed {report_count} reports")
        
        # Example 5: Complex search with multiple criteria
        print("\nSearching for important unread messages...")
        messages = client.get_messages([
            'OR',
            'FROM', 'boss@example.com',
            'SUBJECT', 'urgent',
            'UNSEEN'
        ])
        
        for message_id, email_message in messages:
            print(f"\nImportant message:")
            print(f"  From: {email_message.from_address}")
            print(f"  Subject: {email_message.subject}")
            
            # Save all attachments from important messages
            for attachment in email_message.attachments:
                saved_path = client.save_attachment(
                    attachment,
                    f"important_attachments/{email_message.from_address.split('@')[0]}"
                )
                if saved_path:
                    print(f"  Saved attachment: {saved_path}")
                    
    except Exception as e:
        logger.error(f"Error during processing: {e}")
        
    finally:
        client.disconnect()
        print("\nProcessing complete!")


if __name__ == "__main__":
    main()