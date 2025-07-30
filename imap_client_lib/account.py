"""
Account model for IMAP email accounts.
"""
from dataclasses import dataclass


@dataclass
class Account:
    """
    Represents an IMAP email account configuration.
    """
    name: str
    server: str
    username: str
    password: str
    port: int = 993
    use_ssl: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> 'Account':
        """
        Create an Account instance from a dictionary.
        
        Args:
            data: Dictionary containing account configuration
            
        Returns:
            Account: New Account instance
        """
        return cls(
            name=data.get('name', ''),
            server=data.get('server', ''),
            username=data.get('username', ''),
            password=data.get('password', ''),
            port=data.get('port', 993),
            use_ssl=data.get('use_ssl', True)
        )