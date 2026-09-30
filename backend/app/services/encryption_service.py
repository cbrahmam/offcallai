# backend/app/services/encryption_service.py - NEW FILE
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)

class EncryptionService:
    """Service for encrypting/decrypting API keys securely"""

    # OWASP 2023 recommends 310,000 iterations for PBKDF2-SHA256
    PBKDF2_ITERATIONS = 310000

    @staticmethod
    def _get_encryption_key() -> bytes:
        """Generate encryption key from environment variable"""
        # SECURITY: These MUST be set in production
        password = os.getenv("API_KEY_ENCRYPTION_PASSWORD")
        salt_str = os.getenv("API_KEY_ENCRYPTION_SALT")

        if not password or not salt_str:
            env = os.getenv('ENVIRONMENT', 'development')
            if env != 'development':
                logger.error("CRITICAL: API_KEY_ENCRYPTION_PASSWORD and API_KEY_ENCRYPTION_SALT must be set in production!")
                raise ValueError("Encryption credentials not configured for production")
            # Only use fallback in development
            logger.warning("Using development encryption credentials - NOT SAFE FOR PRODUCTION")
            import secrets
            # Generate consistent dev keys based on a fixed seed (for dev only)
            password = password or "dev-only-password-do-not-use-in-production"
            salt_str = salt_str or "dev-only-salt-do-not-use"

        salt = salt_str.encode()

        # Derive key from password with strong iteration count
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=EncryptionService.PBKDF2_ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    @staticmethod
    def encrypt_api_key(api_key: str) -> str:
        """Encrypt an API key for secure storage"""
        try:
            key = EncryptionService._get_encryption_key()
            fernet = Fernet(key)
            encrypted_key = fernet.encrypt(api_key.encode())
            return base64.urlsafe_b64encode(encrypted_key).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt API key: {e}")
            raise ValueError("Failed to encrypt API key")
    
    @staticmethod
    def decrypt_api_key(encrypted_key: str) -> str:
        """Decrypt an API key for use"""
        try:
            key = EncryptionService._get_encryption_key()
            fernet = Fernet(key)
            encrypted_data = base64.urlsafe_b64decode(encrypted_key.encode())
            decrypted_key = fernet.decrypt(encrypted_data)
            return decrypted_key.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")
            raise ValueError("Failed to decrypt API key")