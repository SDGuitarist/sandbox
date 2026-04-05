import hashlib
import hmac
import secrets
import uuid

from .db import _now


_KEY_PREFIX_LEN = 8   # chars shown in display prefix
_KEY_MIN_LEN = 16     # minimum raw key length accepted by validate_key


def _hash_key(salt: str, raw_key: str) -> str:
    return hashlib.sha256((salt + raw_key).encode()).hexdigest()


def create_key(conn, label: str, service_id: str = None) -> dict:
    """Create an API key. Returns dict including raw key (shown ONCE only).

    The raw key is never stored; only the salted SHA-256 hash is persisted.
    """
    raw_key = secrets.token_hex(32)       # 64-char hex key
    salt = secrets.token_hex(16)
    key_hash = _hash_key(salt, raw_key)
    prefix = raw_key[:_KEY_PREFIX_LEN]
    key_id = str(uuid.uuid4())
    now = _now()

    conn.execute(
        """INSERT INTO api_keys (id, prefix, key_hash, salt, label, service_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (key_id, prefix, key_hash, salt, label, service_id, now),
    )

    return {
        "id": key_id,
        "key": raw_key,   # shown once only
        "prefix": prefix,
        "label": label,
        "service_id": service_id,
        "created_at": now,
    }


def validate_key(conn, raw_key: str) -> dict | None:
    """Validate a raw API key. Returns key metadata or None if invalid/revoked.

    Uses prefix lookup + constant-time hmac.compare_digest.
    Updates last_used_at on success.
    """
    if not raw_key or len(raw_key) < _KEY_MIN_LEN:
        return None

    prefix = raw_key[:_KEY_PREFIX_LEN]
    candidates = conn.execute(
        """SELECT id, key_hash, salt, label, service_id, revoked
           FROM api_keys WHERE prefix = ? AND revoked = 0""",
        (prefix,),
    ).fetchall()

    for candidate in candidates:
        expected = _hash_key(candidate["salt"], raw_key)
        if hmac.compare_digest(expected, candidate["key_hash"]):
            # Update last_used_at
            conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                (_now(), candidate["id"]),
            )
            return {
                "id": candidate["id"],
                "label": candidate["label"],
                "service_id": candidate["service_id"],
            }
    return None


def revoke_key(conn, key_id: str) -> bool:
    """Revoke a key. Returns True if found and revoked."""
    cursor = conn.execute(
        "UPDATE api_keys SET revoked = 1 WHERE id = ? AND revoked = 0",
        (key_id,),
    )
    return cursor.rowcount > 0


def list_keys(conn, service_id: str = None) -> list[dict]:
    """List API keys (never including key material).

    If service_id is given, returns only keys for that service.
    """
    if service_id is not None:
        rows = conn.execute(
            """SELECT id, prefix, label, service_id, created_at, last_used_at, revoked
               FROM api_keys WHERE service_id = ? ORDER BY created_at DESC""",
            (service_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, prefix, label, service_id, created_at, last_used_at, revoked
               FROM api_keys ORDER BY created_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]
