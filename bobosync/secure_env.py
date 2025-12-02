"""
Secure Environment Configuration Manager

This module provides secure storage and retrieval of sensitive environment variables
from .env files, with automatic encryption of passwords and client secrets after first run.

Usage:
    from secure_env import SecureEnvConfig
    
    # Load and decrypt .env file (automatically decrypts if encrypted)
    config = SecureEnvConfig()
    config.load_and_decrypt()
    
    # Encrypt sensitive fields after first run
    config.encrypt_sensitive_fields()
"""

import os
import re
import base64
from pathlib import Path
from typing import Dict, Optional
from cryptography.fernet import Fernet


class SecureEnvConfig:
    """Manages .env file with automatic encryption of sensitive fields"""
    
    # Fields that should be encrypted
    ENCRYPTED_FIELDS = ['PASSWORD', 'CLIENT_SECRET', 'API_KEY', 'SECRET_KEY']
    ENCRYPTED_PREFIX = 'ENCRYPTED:'
    
    def __init__(self, env_path: Optional[str] = None, key_path: Optional[str] = None):
        """
        Initialize secure environment configuration manager
        
        Args:
            env_path: Path to .env file (default: .env in script directory)
            key_path: Path to encryption key file (default: ~/.bobo_encryption_key)
                      Stored in home directory for better security separation
        """
        self.script_dir = Path(__file__).parent
        self.env_path = Path(env_path) if env_path else self.script_dir / '.env'
        
        # Store key in user's home directory for better security separation
        # This prevents both .env and .key from being in the same location
        if key_path:
            self.key_path = Path(key_path)
        else:
            # Check for environment variable override
            env_key_path = os.getenv('BOBO_ENCRYPTION_KEY_PATH')
            if env_key_path:
                self.key_path = Path(env_key_path)
            else:
            # Default to home directory with a hidden, descriptive filename
            # Path.home() works cross-platform:
            # - Windows: C:\Users\Username\.bobo_encryption_key
            # - Mac/Linux: /Users/username/.bobo_encryption_key or /home/username/.bobo_encryption_key
            home_dir = Path.home()
            self.key_path = home_dir / '.bobo_encryption_key'
        
        self._cipher: Optional[Fernet] = None
        
    def _get_or_create_key(self) -> bytes:
        """Get encryption key from file or create new one"""
        if self.key_path.exists():
            with open(self.key_path, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            
            # Ensure parent directory exists (for home directory case)
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write key file
            with open(self.key_path, 'wb') as f:
                f.write(key)
            
            # Set restrictive permissions (Unix/Mac)
            try:
                os.chmod(self.key_path, 0o600)
            except (AttributeError, OSError):
                pass  # Windows doesn't support chmod - that's OK
            
            return key
    
    def _get_cipher(self) -> Fernet:
        """Get cipher instance for encryption/decryption"""
        if self._cipher is None:
            key = self._get_or_create_key()
            self._cipher = Fernet(key)
        return self._cipher
    
    def _encrypt_value(self, value: str) -> str:
        """Encrypt a value"""
        if not value or value.startswith(self.ENCRYPTED_PREFIX):
            return value
        cipher = self._get_cipher()
        encrypted = cipher.encrypt(value.encode())
        return f"{self.ENCRYPTED_PREFIX}{base64.urlsafe_b64encode(encrypted).decode()}"
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a value"""
        if not encrypted_value.startswith(self.ENCRYPTED_PREFIX):
            return encrypted_value
        cipher = self._get_cipher()
        encrypted_part = encrypted_value[len(self.ENCRYPTED_PREFIX):]
        try:
            decoded = base64.urlsafe_b64decode(encrypted_part.encode())
            return cipher.decrypt(decoded).decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}. Check your encryption key.")
    
    def _should_encrypt(self, key: str) -> bool:
        """Check if field should be encrypted"""
        return key.upper() in self.ENCRYPTED_FIELDS
    
    def load_and_decrypt(self) -> Dict[str, str]:
        """
        Load .env file and decrypt encrypted values
        
        Returns:
            Dictionary of environment variables with decrypted values
        """
        if not self.env_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.env_path}\n"
                f"Please create it from .env_safe template"
            )
        
        config = {}
        with open(self.env_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                original_line = line
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Parse KEY=VALUE
                match = re.match(r'^([^=]+)=(.*)$', line)
                if match:
                    key = match.group(1).strip()
                    value = match.group(2).strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # Decrypt if encrypted
                    if value.startswith(self.ENCRYPTED_PREFIX):
                        try:
                            config[key] = self._decrypt_value(value)
                        except ValueError as e:
                            print(f"Warning: Could not decrypt {key} at line {line_num}: {e}")
                            config[key] = None
                    else:
                        config[key] = value
        
        return config
    
    def encrypt_sensitive_fields(self) -> int:
        """
        Encrypt sensitive fields in .env file after first run
        
        This should be called after loading the config to encrypt any plaintext
        sensitive values. Automatically detects if a sensitive field is in plaintext
        (doesn't start with ENCRYPTED:) and encrypts it.
        
        This allows users to manually edit .env file with plaintext values, and
        the system will automatically encrypt them on the next run.
        
        Returns:
            Number of fields encrypted
        """
        if not self.env_path.exists():
            return 0
        
        lines = []
        modified = False
        encrypted_count = 0
        
        with open(self.env_path, 'r', encoding='utf-8') as f:
            for line in f:
                original_line = line
                stripped = line.strip()
                
                # Preserve comments and empty lines
                if not stripped or stripped.startswith('#'):
                    lines.append(line)
                    continue
                
                # Parse KEY=VALUE
                match = re.match(r'^([^=]+)=(.*)$', stripped)
                if match:
                    key = match.group(1).strip()
                    value = match.group(2).strip()
                    
                    # Remove quotes if present for processing
                    quoted = False
                    quote_char = None
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                        quoted = True
                        quote_char = '"'
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                        quoted = True
                        quote_char = "'"
                    
                    # Encrypt if sensitive and not already encrypted
                    if self._should_encrypt(key) and value and not value.startswith(self.ENCRYPTED_PREFIX):
                        encrypted = self._encrypt_value(value)
                        # Preserve original formatting (quotes, spacing)
                        if quoted:
                            lines.append(f"{key}={quote_char}{encrypted}{quote_char}\n")
                        else:
                            lines.append(f"{key}={encrypted}\n")
                        modified = True
                        encrypted_count += 1
                    else:
                        lines.append(original_line)
                else:
                    lines.append(original_line)
        
        # Write back if modified
        if modified:
            with open(self.env_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            # Set restrictive permissions (Unix/Mac)
            try:
                os.chmod(self.env_path, 0o600)
            except (AttributeError, OSError):
                pass  # Windows doesn't support chmod - that's OK
            print(f"✓ Encrypted {encrypted_count} sensitive field(s) in {self.env_path}")
        
        return encrypted_count
    
    def set_env_vars(self, config: Dict[str, str]):
        """
        Set environment variables from decrypted config
        
        This allows the decrypted values to be used with python-dotenv's load_dotenv()
        or directly via os.environ
        
        Args:
            config: Dictionary of environment variables
        """
        for key, value in config.items():
            if value is not None:
                os.environ[key] = value


def load_secure_env(env_path: Optional[str] = None, key_path: Optional[str] = None, auto_encrypt: bool = True) -> Dict[str, str]:
    """
    Convenience function to load and decrypt .env file
    
    Args:
        env_path: Path to .env file (default: .env in script directory)
        key_path: Path to encryption key file (default: ~/.bobo_encryption_key)
        auto_encrypt: If True, encrypt sensitive fields after loading (first run)
        
    Returns:
        Dictionary of environment variables with decrypted values
    """
    secure_config = SecureEnvConfig(env_path, key_path)
    config = secure_config.load_and_decrypt()
    
    # Encrypt sensitive fields if they're still in plaintext (first run)
    if auto_encrypt:
        encrypted_count = secure_config.encrypt_sensitive_fields()
        if encrypted_count > 0:
            # Reload to get encrypted values (though we already have decrypted ones)
            # This is mainly to update the file
            pass
    
    return config

