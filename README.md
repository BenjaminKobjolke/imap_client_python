# IMAP Client Library

A simple and reusable IMAP client library for Python that makes it easy to work with email messages and attachments.

## Features

- Simple and intuitive API
- Support for multiple IMAP accounts
- Email message parsing with attachment handling
- Folder management (create, move, delete)
- Flexible message processing with callbacks
- Built-in logging support
- Type hints for better IDE support

## Installation

Install from GitHub:

```bash
pip install git+https://github.com/BenjaminKobjolke/imap_client_python.git
```

Or clone and install from source:

```bash
git clone https://github.com/BenjaminKobjolke/imap_client_python.git
cd imap_client_python
pip install .
```

## Quick Start

```python
from imap_client_lib import ImapClient, Account

# Create an account configuration
account = Account(
    name="My Email",
    server="imap.gmail.com",
    username="your.email@gmail.com",
    password="your_password",
    port=993,
    use_ssl=True
)

# Create the IMAP client
client = ImapClient(account)

# Connect to the server
if client.connect():
    # Get unread messages
    messages = client.get_unread_messages()
    
    for message_id, email_message in messages:
        print(f"From: {email_message.from_address}")
        print(f"Subject: {email_message.subject}")
        
        # Get email body
        body_text = email_message.get_body()
        if body_text:
            print(f"Body: {body_text[:100]}...")  # Show first 100 chars
        
        # Process attachments
        for attachment in email_message.attachments:
            print(f"Attachment: {attachment.filename}")
            # Save attachment
            saved_path = client.save_attachment(attachment, "/path/to/save/")
            
        # Mark as read
        client.mark_as_read(message_id)
        
    # Disconnect
    client.disconnect()
```

## Advanced Usage

### Custom Search Criteria

```python
# Search for messages from a specific sender
messages = client.get_messages(['FROM', 'sender@example.com'])

# Search for messages with specific subject
messages = client.get_messages(['SUBJECT', 'Important'])

# Complex search criteria
messages = client.get_messages(['OR', 'FROM', 'sender1@example.com', 'FROM', 'sender2@example.com'])
```

### Processing Messages with Callbacks

```python
def process_email(email_message):
    """Process individual email messages"""
    if "invoice" in email_message.subject.lower():
        for attachment in email_message.attachments:
            if attachment.filename.endswith('.pdf'):
                # Process PDF invoice
                print(f"Processing invoice: {attachment.filename}")
                return True
    return False

# Process messages with custom callback
processed_count = client.process_messages_with_callback(
    callback=process_email,
    search_criteria=['UNSEEN'],
    mark_as_read=True,
    move_to_folder='Processed'
)
```

### Working with Folders

```python
# List all folders
folders = client.list_folders()
print("Available folders:", folders)

# Move message to a folder
client.move_to_folder(message_id, "Archive")

# Delete a message
client.delete_message(message_id)
```

### Using with Logging

```python
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pass logger to client
client = ImapClient(account, logger=logger)
```

## API Reference

### Account

The `Account` class represents an IMAP account configuration:

- `name`: Display name for the account
- `server`: IMAP server hostname
- `username`: Login username
- `password`: Login password
- `port`: IMAP port (default: 993)
- `use_ssl`: Whether to use SSL (default: True)
- `target_folder`: Optional default folder for operations
- `imap_move_folder`: Optional folder to move processed messages to

### ImapClient

Main methods:

- `connect()`: Connect to the IMAP server
- `disconnect()`: Disconnect from the server
- `get_messages(search_criteria, folder)`: Get messages based on search criteria
- `get_unread_messages()`: Get all unread messages from inbox
- `mark_as_read(message_id)`: Mark a message as read
- `mark_as_unread(message_id)`: Mark a message as unread
- `move_to_folder(message_id, folder)`: Move a message to a folder
- `delete_message(message_id)`: Delete a message
- `list_folders()`: List all available folders
- `save_attachment(attachment, target_path)`: Save an attachment to disk
- `process_messages_with_callback(callback, ...)`: Process messages with custom logic

### EmailMessage

The `EmailMessage` class contains:

- `message_id`: Unique message identifier
- `from_address`: Sender's email address
- `subject`: Email subject
- `date`: Email date
- `attachments`: List of `Attachment` objects
- `raw_message`: Raw email.message.Message object
- `get_body(content_type="text/plain")`: Extract email body content (text/plain or text/html)

### Attachment

The `Attachment` class contains:

- `filename`: Name of the attachment
- `content_type`: MIME content type
- `data`: Raw attachment data as bytes

## Extending the Library

The library is designed to be easily extensible. You can extend the `Account` class to add application-specific fields:

```python
from dataclasses import dataclass
from typing import Optional
from imap_client_lib import Account, ImapClient

@dataclass
class MyCustomAccount(Account):
    """Extended account with application-specific fields"""
    target_folder: Optional[str] = None
    auto_archive: bool = False
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MyCustomAccount':
        return cls(
            # Base Account fields
            name=data.get('name', ''),
            server=data.get('server', ''),
            username=data.get('username', ''),
            password=data.get('password', ''),
            port=data.get('port', 993),
            use_ssl=data.get('use_ssl', True),
            # Custom fields
            target_folder=data.get('target_folder'),
            auto_archive=data.get('auto_archive', False)
        )

# Use with ImapClient as normal
account = MyCustomAccount.from_dict(config)
client = ImapClient(account)  # Works seamlessly!
```

You can also extend the `ImapClient` class to add custom functionality that uses your extended account fields. See `examples/extending_account.py` for a complete example.

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.