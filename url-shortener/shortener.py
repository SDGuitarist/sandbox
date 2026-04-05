import secrets
import string

CHARSET = string.ascii_letters + string.digits  # 62 chars
CODE_LEN = 6
MAX_RETRIES = 5


def generate_code():
    """Generate a random 6-character base62 short code using a CSPRNG."""
    return ''.join(secrets.choice(CHARSET) for _ in range(CODE_LEN))
