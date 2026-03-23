"""
Security Utilities - Encryption and Decryption
"""
from cryptography.fernet import Fernet
from backend.config import ENCRYPTION_KEY
import logging

logger = logging.getLogger(__name__)

# Initialize cipher with validation
if not ENCRYPTION_KEY:
    logger.error("CRITICAL: ENCRYPTION_KEY is not set!")
    logger.error("Set ENCRYPTION_KEY environment variable or add it to .env file")
    raise ValueError("ENCRYPTION_KEY is required for security. See logs for details.")

try:
    cipher = Fernet(ENCRYPTION_KEY)
    logger.debug("Encryption cipher initialized successfully")
except Exception as e:
    logger.error(f"CRITICAL: Invalid ENCRYPTION_KEY format: {e}")
    logger.error("The key must be a valid Fernet key (32 URL-safe base64-encoded bytes)")
    raise ValueError(f"Invalid encryption key: {e}")


def encrypt_data(data: str) -> bytes:
    """Encrypt string data"""
    return cipher.encrypt(data.encode())


def decrypt_data(encrypted_data: bytes) -> str:
    """Decrypt bytes data"""
    return cipher.decrypt(encrypted_data).decode()


def encrypt_json(data: dict) -> bytes:
    """Encrypt dictionary as JSON"""
    import json
    return cipher.encrypt(json.dumps(data).encode())


def decrypt_json(encrypted_data: bytes) -> dict:
    """Decrypt bytes to dictionary"""
    import json
    decrypted = cipher.decrypt(encrypted_data).decode()
    return json.loads(decrypted)
