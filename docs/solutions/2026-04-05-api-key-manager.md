---
title: "API Key Management Service"
date: 2026-04-05
tags: [flask, sqlite, api-keys, rate-limiting, authentication, hmac, python]
---

# API Key Management Service — Solution Doc

## Problem Solved
Flask REST API that generates API keys (`ak_<32 base62 chars>`), associates per-key rate limits (fixed window, RPM), validates keys with constant-time comparison, and tracks usage stats. Keys are hashed with a per-key salt — plaintext is never stored.

## Key Decisions

### Salted SHA-256 for key storage (not plaintext, not unsalted hash, not PBKDF2)
API keys are 190-bit random values — the key space is so large that brute force is infeasible. But unsalted SHA-256 allows rainbow table attacks on a leaked DB. PBKDF2 (100k iterations) is unnecessarily slow for per-request validation. The right choice: **salted SHA-256** (fast + rainbow-table-resistant).

```python
def generate_salt() -> str:
    return secrets.token_hex(16)

def hash_key(key: str, salt: str) -> str:
    return hashlib.sha256((salt + key).encode()).hexdigest()

def verify_key(key: str, salt: str, stored_hash: str) -> bool:
    computed = hashlib.sha256((salt + key).encode()).hexdigest()
    return hmac.compare_digest(computed, stored_hash)  # constant-time
```

### Prefix-based lookup + constant-time comparison (not hash-index lookup)
Since the hash depends on the salt (which varies per key), you can't look up by hash directly. Instead:
1. Store a 16-char lookup prefix in an indexed column
2. Fetch all candidates matching the prefix (near-zero collision probability at scale)
3. For each candidate, compute salted hash and compare with `hmac.compare_digest`

```python
candidates = db.execute('SELECT * FROM api_keys WHERE prefix=?', (lookup_prefix(key),)).fetchall()
row = next((c for c in candidates if verify_key(key, c['key_salt'], c['key_hash'])), None)
```

Display prefix (8 chars, shown to users) is separate from lookup prefix (16 chars, stored in DB).

### `BEGIN IMMEDIATE` makes rate limit window reset + increment atomic
Two separate `db.execute()` calls with `db.commit()` between them are two separate transactions — another request can interleave. Fix: acquire the write lock upfront.

```python
db.execute('BEGIN IMMEDIATE')  # Acquires write lock — both steps are now one atomic unit
db.execute(...)  # Step 1: reset expired window
db.execute(...)  # Step 2: check-and-increment
db.commit()
```

### `expires_at` must be normalized to `YYYY-MM-DD HH:MM:SS` before storage
SQLite's `datetime()` function does not recognize ISO8601 `T`-separator (`2026-01-01T00:00:00Z` → NULL). Always normalize at write time using Python's `datetime.fromisoformat()`:

```python
dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
expires_at = dt.strftime('%Y-%m-%d %H:%M:%S')
```

Compare with string comparison (not SQL datetime functions) in Python:
```python
if row['expires_at'] and row['expires_at'] <= datetime.now(utc).strftime('%Y-%m-%d %H:%M:%S'):
    return 401 expired
```

### Return raw key only at creation; never again
```python
# POST /keys 201 — one-time key exposure
result = key_to_dict(row)  # no key/salt/hash
result['key'] = key        # add raw key for this response only
```
`key_to_dict()` never includes `key`, `key_hash`, or `key_salt`. Enforce in the serializer, not at each call site.

### Rate limit: fixed window counter in the key row (no separate table)
```sql
window_count    INTEGER NOT NULL DEFAULT 0
window_start    TIMESTAMP
```
Window reset is idempotent (safe for concurrent calls):
```sql
UPDATE api_keys SET window_count=0, window_start=CURRENT_TIMESTAMP
WHERE id=? AND (window_start IS NULL OR elapsed_seconds >= 60)
```
Then check-and-increment (both in one `BEGIN IMMEDIATE` transaction):
```sql
UPDATE api_keys SET window_count=window_count+1, total_requests=total_requests+1
WHERE id=? AND window_count < rate_limit_rpm
-- rowcount=0 → rate limited (429); rowcount=1 → success
```
`rate_limit_rpm=0` = unlimited (skip both steps, just track total).

### Validate `expires_at` is in the future at creation time
A key with a past `expires_at` is immediately invalid — return 400 with a clear error rather than silently creating an unusable key.

### Name length cap prevents DoS via unbounded payloads
```python
if len(name) > 255:
    return jsonify({'error': 'name must be 255 characters or fewer'}), 400
```

## Risk Resolution
- **Risk tracked:** Atomic rate limit check via UPDATE — TOCTOU-safe?
- **What actually happened:** The two-step approach (separate transactions) was technically TOCTOU-raceable. `BEGIN IMMEDIATE` was added to acquire the write lock upfront, making both steps atomic within a single transaction.
- **Lesson:** Two consecutive `db.commit()` calls are two separate transactions. For operations that must be atomic together (read-validate-write patterns), use `BEGIN IMMEDIATE` to hold the write lock across all steps.

## Schema
```sql
api_keys(id, key_hash, key_salt, prefix TEXT INDEXED, name, is_active,
         rate_limit_rpm, window_count, window_start, total_requests,
         last_used_at, created_at, expires_at)
```

## API Surface
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/keys` | POST | Create key — returns raw key ONCE |
| `/keys` | GET | List all keys (no raw key) |
| `/keys/<id>` | GET | Key details (no raw key) |
| `/keys/<id>` | DELETE | Soft-revoke |
| `/keys/validate` | POST | Validate key + check rate limit + increment counter |
| `/keys/<id>/stats` | GET | Usage stats with `rate_limited` boolean |
