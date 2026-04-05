---
title: "API Key Management Service"
date: 2026-04-05
status: ready
brainstorm: "docs/brainstorms/2026-04-05-api-key-manager.md"
feed_forward:
  risk: "Atomic rate limit check via UPDATE WHERE window_count < rate_limit_rpm — is it truly TOCTOU-safe in SQLite?"
  verify_first: true
---

# API Key Management Service — Plan

## What exactly is changing?
A new Flask application in `/workspace/api-key-manager/` with 6 endpoints backed by a SQLite database. Provides API key lifecycle management and rate-limit validation for external services to integrate against.

## What must NOT change?
- `/workspace/job-queue/`, `/workspace/url-shortener/`, `/workspace/webhook-delivery/` must not be modified.
- No external dependencies beyond Flask and Python stdlib (uuid, sqlite3, json, secrets, hashlib, datetime).

## How will we know it worked?
1. `POST /keys` returns 201 with a full key (`ak_<32chars>`) and `id`. Subsequent `GET /keys/<id>` does NOT return the key value.
2. `POST /keys/validate` with the correct key returns 200 `{"valid": true, "key_id": "..."}`.
3. `POST /keys/validate` with a wrong key returns 401.
4. `POST /keys/validate` called `rate_limit_rpm+1` times within one window returns 429 on the last call.
5. After `DELETE /keys/<id>`, `POST /keys/validate` returns 401.
6. An expired key (`expires_at` in the past) returns 401.
7. `GET /keys/<id>/stats` returns `total_requests`, `last_used_at`, `window_count`.

## What is the most likely way this plan is wrong?
The atomic rate limit UPDATE may not behave as expected for the window reset case: when the window has expired, we must reset `window_start` and `window_count` before checking. If two concurrent requests hit an expired window simultaneously, both could reset and both could increment — resulting in both succeeding even if `rate_limit_rpm=1`. Mitigation: use a two-step approach in SQLite with the write lock: reset expired window first (UPDATE WHERE window_start < cutoff), then check-and-increment.

---

## File Structure

```
/workspace/api-key-manager/
├── app.py           # Flask app + all routes
├── database.py      # SQLite connection (WAL + verify), schema, init
├── keys.py          # Key generation + hashing helpers
└── requirements.txt # Flask only
```

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS api_keys (
    id              TEXT PRIMARY KEY,
    key_hash        TEXT NOT NULL UNIQUE,
    prefix          TEXT NOT NULL,
    name            TEXT NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1,
    rate_limit_rpm  INTEGER NOT NULL DEFAULT 60,
    window_count    INTEGER NOT NULL DEFAULT 0,
    window_start    TIMESTAMP,
    total_requests  INTEGER NOT NULL DEFAULT 0,
    last_used_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
```

## `keys.py`

```python
import secrets, string, hashlib

CHARSET = string.ascii_letters + string.digits
KEY_PREFIX = 'ak_'
KEY_RANDOM_LEN = 32

def generate_key() -> str:
    """Generate a new API key: ak_<32 random base62 chars>."""
    return KEY_PREFIX + ''.join(secrets.choice(CHARSET) for _ in range(KEY_RANDOM_LEN))

def hash_key(key: str) -> str:
    """SHA-256 hash of the key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()

def key_prefix(key: str) -> str:
    """First 8 chars for display."""
    return key[:8]
```

## Endpoints (`app.py`)

### POST /keys
- Body: `{"name": "...", "rate_limit_rpm": 60, "expires_at": null}`
- Validate: `name` required; `rate_limit_rpm` >= 0 int (0 = unlimited); `expires_at` optional ISO8601 string
- Generate key with `generate_key()`; store `hash_key(key)` and `key_prefix(key)`
- Return 201: `{"id": "...", "key": "ak_...", "prefix": "ak_xxxxx", "name": "...", "rate_limit_rpm": 60, "created_at": "..."}` — key appears in response ONLY HERE
- All subsequent responses use `key_to_dict()` which excludes `key`

### GET /keys
- Return list of all keys (no key value, show `prefix`, `name`, `is_active`, stats)

### GET /keys/<id>
- Return single key details (no key value), 404 if not found

### DELETE /keys/<id>
- Set `is_active=0` — soft revoke
- Return 200: `{"id": "...", "is_active": false}`

### POST /keys/validate
- Body: `{"key": "ak_..."}`
- Hash the provided key with `hash_key()`
- Look up by `key_hash`
- If not found: return 401 `{"valid": false, "error": "invalid key"}`
- If `is_active=0`: return 401 `{"valid": false, "error": "key revoked"}`
- If `expires_at` is not null and `expires_at < now`: return 401 `{"valid": false, "error": "key expired"}`
- Rate limit check (if `rate_limit_rpm > 0`):
  - Step 1: If current window has expired, reset: `UPDATE api_keys SET window_count=0, window_start=CURRENT_TIMESTAMP WHERE id=? AND (window_start IS NULL OR CAST((julianday('now')-julianday(window_start))*86400 AS INTEGER) >= 60)`
  - Step 2: Atomically check-and-increment: `UPDATE api_keys SET window_count=window_count+1, total_requests=total_requests+1, last_used_at=CURRENT_TIMESTAMP WHERE id=? AND window_count < rate_limit_rpm`
  - Check `cursor.rowcount`: 0 = rate limited → return 429; 1 = success
- If `rate_limit_rpm=0`: skip window check, just increment `total_requests` + `last_used_at`
- Return 200: `{"valid": true, "key_id": "...", "name": "...", "rate_limit_rpm": N, "window_count": N, "total_requests": N}`

### GET /keys/<id>/stats
- Return usage stats: `total_requests`, `last_used_at`, `window_count`, `window_start`, `rate_limit_rpm`

## Rate Limit Atomicity Detail
The two-step approach (reset expired window → check-and-increment) is safe under SQLite's serialized writes:
- Two concurrent requests on an expired window both issue the reset UPDATE — only the one with the write lock succeeds; the second's UPDATE is a no-op (window already reset by the first)
- Then both issue the check-and-increment — if `rate_limit_rpm=1`, only the first succeeds (rowcount=1); the second gets rowcount=0 and returns 429

## Implementation Order
1. `requirements.txt`
2. `keys.py` — pure functions, no deps
3. `database.py` — get_db, close_db, init_db, schema
4. `app.py` — all routes + error handlers

## Feed-Forward
- **Hardest decision:** Atomic rate limit across expired-window reset + increment. Chose two-step UPDATE approach: first reset if expired (idempotent), then check-and-increment.
- **Rejected alternatives:** Separate usage_log table (deferred), sliding window (complex), Redis (out of scope).
- **Least confident:** The window reset UPDATE followed by the check-and-increment UPDATE — these are two separate SQL statements. Under high concurrency, a reset from request A followed by an increment from request B could race. Since SQLite serializes writes, this is safe — but need to verify the window_start comparison handles NULL correctly (first-ever use).
