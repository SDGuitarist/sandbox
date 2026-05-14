import hmac
import hashlib
import base64
import os

SQUARE_SIGNATURE_KEY = os.environ.get("SQUARE_WEBHOOK_SIGNATURE_KEY", "")
SQUARE_WEBHOOK_URL = os.environ.get("SQUARE_WEBHOOK_URL", "")


def verify_square_signature(body: str, signature: str) -> bool:
    if not SQUARE_SIGNATURE_KEY or not SQUARE_WEBHOOK_URL:
        return False
    combined = SQUARE_WEBHOOK_URL + body
    expected = base64.b64encode(
        hmac.new(
            SQUARE_SIGNATURE_KEY.encode("utf-8"),
            combined.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected, signature)
