"""
A simple and reusable IMAP client library for Python.
"""

from .client import ImapClient
from .account import Account
from .email_message import EmailMessage, Attachment

__version__ = "0.1.0"
__all__ = ["ImapClient", "Account", "EmailMessage", "Attachment"]