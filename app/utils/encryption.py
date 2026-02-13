"""
Encryption utilities for sensitive data fields.
"""
import os
import base64
import hashlib
from typing import Tuple, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from app.configs.settings import settings


class EncryptionService:
    """Service for encrypting and decrypting sensitive data fields."""
    
    def __init__(self, key: Optional[str] = None):
        """
        Initialize encryption service.
        
        Args:
            key: Base64-encoded encryption key. If None, uses SECRET_KEY from settings.
        """
        if key is None:
            # Derive key from SECRET_KEY
            self.key = self._derive_key(settings.secret_key.encode())
        else:
            self.key = base64.b64decode(key)
        
        # Validate key length (must be 32 bytes for AES-256)
        if len(self.key) != 32:
            raise ValueError("Encryption key must be 32 bytes for AES-256")
    
    @staticmethod
    def _derive_key(password: bytes, salt: Optional[bytes] = None) -> bytes:
        """
        Derive a 32-byte encryption key from a password using PBKDF2.
        
        Args:
            password: Password to derive key from
            salt: Salt for key derivation (default: constant salt)
        
        Returns:
            32-byte encryption key
        """
        if salt is None:
            # Use a constant salt (in production, this should be per-environment)
            salt = b"maas_encryption_salt_v1"
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        return kdf.derive(password)
    
    def encrypt(self, plaintext: str) -> Tuple[str, str]:
        """
        Encrypt a plaintext string using AES-256-GCM.
        
        Args:
            plaintext: String to encrypt
        
        Returns:
            Tuple of (ciphertext_base64, nonce_base64)
        """
        # Generate random nonce (12 bytes for GCM)
        nonce = os.urandom(12)
        
        # Create AESGCM cipher
        aesgcm = AESGCM(self.key)
        
        # Encrypt data
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        
        # Return base64-encoded ciphertext and nonce
        return (
            base64.b64encode(ciphertext).decode('utf-8'),
            base64.b64encode(nonce).decode('utf-8')
        )
    
    def decrypt(self, ciphertext_b64: str, nonce_b64: str) -> str:
        """
        Decrypt a ciphertext string using AES-256-GCM.
        
        Args:
            ciphertext_b64: Base64-encoded ciphertext
            nonce_b64: Base64-encoded nonce
        
        Returns:
            Decrypted plaintext string
        
        Raises:
            ValueError: If decryption fails (invalid ciphertext or key)
        """
        # Decode base64
        ciphertext = base64.b64decode(ciphertext_b64)
        nonce = base64.b64decode(nonce_b64)
        
        # Create AESGCM cipher
        aesgcm = AESGCM(self.key)
        
        # Decrypt data
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")
    
    def encrypt_field(self, value: str) -> dict:
        """
        Encrypt a field value and return metadata.
        
        Args:
            value: Value to encrypt
        
        Returns:
            Dict with ciphertext, nonce, algorithm, and version
        """
        ciphertext, nonce = self.encrypt(value)
        
        return {
            "ciphertext": ciphertext,
            "nonce": nonce,
            "algorithm": "AES-256-GCM",
            "version": "1",
        }
    
    def decrypt_field(self, encrypted_data: dict) -> str:
        """
        Decrypt a field value from metadata.
        
        Args:
            encrypted_data: Dict with ciphertext and nonce
        
        Returns:
            Decrypted plaintext value
        """
        return self.decrypt(
            encrypted_data["ciphertext"],
            encrypted_data["nonce"]
        )
    
    @staticmethod
    def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
        """
        Mask sensitive data for logging.
        
        Args:
            data: Sensitive string to mask
            visible_chars: Number of characters to show at the end
        
        Returns:
            Masked string (e.g., "****abcd")
        """
        if len(data) <= visible_chars:
            return "*" * len(data)
        
        return "*" * (len(data) - visible_chars) + data[-visible_chars:]


# Global encryption service instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Get the global encryption service instance.
    
    Returns:
        EncryptionService: Singleton encryption service
    """
    global _encryption_service
    
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    
    return _encryption_service


def encrypt_api_key(api_key: str) -> dict:
    """
    Encrypt an API key for storage.
    
    Args:
        api_key: Plain API key
    
    Returns:
        Encrypted field metadata
    """
    service = get_encryption_service()
    return service.encrypt_field(api_key)


def decrypt_api_key(encrypted_data: dict) -> str:
    """
    Decrypt an API key from storage.
    
    Args:
        encrypted_data: Encrypted field metadata
    
    Returns:
        Plain API key
    """
    service = get_encryption_service()
    return service.decrypt_field(encrypted_data)


def hash_for_lookup(value: str) -> str:
    """
    Hash a value for database lookup (one-way).
    
    Args:
        value: Value to hash
    
    Returns:
        SHA-256 hex digest
    """
    return hashlib.sha256(value.encode()).hexdigest()
