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


def safe_resolve_path(untrusted_path: str, allowed_root: "Path") -> "Path":
    """Resolve *untrusted_path* and verify it falls within *allowed_root*.

    Raises ValueError on traversal attempts.
    """
    from pathlib import Path as _Path
    resolved = _Path(untrusted_path).resolve()
    allowed = _Path(allowed_root).resolve()
    if not str(resolved).startswith(str(allowed) + "/") and resolved != allowed:
        raise ValueError("Path is outside the allowed directory")
    return resolved


def encrypt_data(data: str) -> str:
    """Encrypt string data, returns base64-encoded string suitable for Text columns"""
    return cipher.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data) -> str:
    """Decrypt encrypted data (accepts str or bytes)"""
    if isinstance(encrypted_data, str):
        encrypted_data = encrypted_data.encode()
    return cipher.decrypt(encrypted_data).decode()


def encrypt_json(data: dict) -> str:
    """Encrypt dictionary as JSON, returns base64-encoded string suitable for Text columns"""
    import json
    return cipher.encrypt(json.dumps(data).encode()).decode()


def decrypt_json(encrypted_data) -> dict:
    """Decrypt to dictionary (accepts str or bytes)"""
    import json
    if isinstance(encrypted_data, str):
        encrypted_data = encrypted_data.encode()
    decrypted = cipher.decrypt(encrypted_data).decode()
    return json.loads(decrypted)
