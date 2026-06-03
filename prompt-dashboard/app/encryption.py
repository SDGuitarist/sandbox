from cryptography.fernet import Fernet
from flask import current_app

_fernet = None


def get_fernet():
    """Get Fernet instance. Cached per process.

    Requires an active Flask application context (uses current_app.config).
    Raises RuntimeError if called outside an application context.

    The singleton is cached for the lifetime of the process. If
    PROMPT_ENCRYPTION_KEY is rotated, the process must be restarted.
    """
    global _fernet
    if _fernet is None:
        key = current_app.config['PROMPT_ENCRYPTION_KEY']
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_field(plaintext):
    """Encrypt a string. Returns base64-encoded ciphertext string.

    Empty strings are stored as empty (no encryption needed).
    Requires an active Flask application context.
    """
    if not plaintext:
        return ''
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext):
    """Decrypt a ciphertext string. Returns plaintext.

    Empty strings return empty.
    Requires an active Flask application context.
    """
    if not ciphertext:
        return ''
    return get_fernet().decrypt(ciphertext.encode()).decode()
