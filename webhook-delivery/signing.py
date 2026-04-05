import hmac
import hashlib
import json


def sign_payload(secret: str, payload: dict) -> str:
    """Generate HMAC-SHA256 signature for a webhook payload."""
    body = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"sha256={sig}"
