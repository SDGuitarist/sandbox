import hashlib
import hmac
import secrets
import string

CHARSET = string.ascii_letters + string.digits
KEY_PREFIX = 'ak_'
KEY_RANDOM_LEN = 32

# Prefix lengths
DISPLAY_PREFIX_LEN = 8   # shown to users: "ak_XXXXX"
LOOKUP_PREFIX_LEN = 16   # stored for DB lookup (more chars → near-zero collision probability)


def generate_key() -> str:
    """Generate a new API key: ak_<32 random base62 chars>."""
    return KEY_PREFIX + ''.join(secrets.choice(CHARSET) for _ in range(KEY_RANDOM_LEN))


def generate_salt() -> str:
    """Generate a random 32-hex-char salt for key hashing."""
    return secrets.token_hex(16)


def hash_key(key: str, salt: str) -> str:
    """Salted SHA-256 of the key for storage.
    API keys are 190-bit random — salted SHA-256 is sufficient (no PBKDF2 needed).
    Never call with an empty salt."""
    return hashlib.sha256((salt + key).encode()).hexdigest()


def verify_key(key: str, salt: str, stored_hash: str) -> bool:
    """Constant-time comparison to prevent timing side-channel attacks."""
    computed = hashlib.sha256((salt + key).encode()).hexdigest()
    return hmac.compare_digest(computed, stored_hash)


def display_prefix(key: str) -> str:
    """First 8 chars of the key shown to users for identification."""
    return key[:DISPLAY_PREFIX_LEN]


def lookup_prefix(key: str) -> str:
    """First 16 chars used as a DB lookup index (avoids full-table scan)."""
    return key[:LOOKUP_PREFIX_LEN]
