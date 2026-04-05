---
title: "Webhook Delivery System with Flask + SQLite"
date: 2026-04-05
tags: [flask, sqlite, webhooks, exponential-backoff, delivery-queue, hmac, python]
---

# Webhook Delivery System — Solution Doc

## Problem Solved
Flask REST API that accepts webhook registrations, fans out events to matching active webhooks, and delivers them via a worker polling system with exponential backoff retries and timeout recovery.

## Key Decisions

### Embed queue logic directly — do not call the job-queue API
The existing job-queue service cannot schedule deliveries for a future time (`next_attempt_at`). Exponential backoff requires scheduling future retries. Solution: self-contained app with `deliveries` table and embedded claim/timeout logic. Cost: duplicates ~30 lines of claim code. Benefit: independent deployment, full query access to delivery history.

### Per-webhook `max_attempts` stored in the `webhooks` table
Register `max_attempts` per-webhook at registration time, store it in the `webhooks` row, and copy it into each `delivery` row at fan-out time. Never hardcode a global default in the fan-out INSERT.

```python
# Wrong — hardcodes 5 regardless of webhook setting:
db.execute('INSERT INTO deliveries (..., max_attempts) VALUES (?, ?, ?, ?, 5)', ...)

# Right — copies from webhook row:
db.execute('INSERT INTO deliveries (..., max_attempts) VALUES (?, ?, ?, ?, ?)',
           (..., webhook['max_attempts']))
```

### Retry boundary: `attempt_count + 1 < max_attempts`
`attempt_count` is 0-indexed and incremented after each failure. Check BEFORE incrementing:

```python
if attempt_count + 1 < max_attempts:
    # retry — attempts remain after this one
else:
    # failed permanently — this was the last attempt
```

With `max_attempts=3`:
- attempt_count=0 → `1 < 3` → retry (1st failure, 2 more allowed)
- attempt_count=1 → `2 < 3` → retry (2nd failure, 1 more allowed)
- attempt_count=2 → `3 < 3` → False → failed (3rd failure, exhausted)

**Do not use `attempt_count < max_attempts`** — that allows one extra retry.

### Use `claimed_at` (not `next_attempt_at`) as the stale worker timeout anchor
The stale worker detection query must measure how long a worker has been silent since it *claimed* the delivery, not since it was *scheduled*. `next_attempt_at` is the scheduling time — for retried deliveries it could be in the past or future. Always add `claimed_at TIMESTAMP` to the deliveries table and set it during the claim UPDATE.

```python
# Wrong anchor:
AND CAST((julianday('now') - julianday(next_attempt_at)) * 86400 AS INTEGER) >= 300

# Right anchor:
AND claimed_at IS NOT NULL
AND CAST((julianday('now') - julianday(claimed_at)) * 86400 AS INTEGER) >= 300
```

### Atomic claim: SELECT id → UPDATE WHERE id AND status='pending' → fetch by id
Identical to job-queue solution doc — always fetch the claimed row by its specific `id`, never by `worker_id`:

```python
pending = db.execute(
    "SELECT id FROM deliveries WHERE status='pending' AND next_attempt_at <= datetime('now') "
    "ORDER BY next_attempt_at ASC LIMIT 1"
).fetchone()
# ... then:
cursor = db.execute(
    "UPDATE deliveries SET status='delivering', worker_id=?, claimed_at=CURRENT_TIMESTAMP "
    "WHERE id=? AND status='pending'", (worker_id, delivery_id)
)
if cursor.rowcount == 0:
    return '', 204  # Another worker got it first
row = db.execute('SELECT * FROM deliveries WHERE id=?', (delivery_id,)).fetchone()
```

### Exponential backoff with SQLite datetime arithmetic
```python
delay = BASE_BACKOFF_SECONDS * (2 ** attempt_count)  # 10, 20, 40, 80...
db.execute(
    "UPDATE deliveries SET next_attempt_at=datetime('now', ? || ' seconds') WHERE id=?",
    (f'+{delay}', delivery_id)
)
```
SQLite concatenates `'+10'` + `' seconds'` → `'+10 seconds'` which is a valid datetime modifier.

### Return `secret` only at registration; redact from all subsequent responses
```python
def webhook_to_dict(row):
    return {
        'id': row['id'], 'url': row['url'], 'events': ...,  # no 'secret'
    }

# POST /webhooks 201 response — one-time secret exposure:
result = webhook_to_dict(row)
result['secret'] = row['secret']
return jsonify(result), 201
```

### Index on (status, next_attempt_at) for claim query efficiency
```sql
CREATE INDEX IF NOT EXISTS idx_deliveries_status_next ON deliveries(status, next_attempt_at);
```
The claim query filters `WHERE status='pending' AND next_attempt_at <= datetime('now') ORDER BY next_attempt_at ASC` — this index makes it a range scan instead of a full table scan.

### WAL mode + verify (inherited from prior art)
Same pattern as job-queue: `PRAGMA journal_mode=WAL` + verify the return value is `'wal'`. See job-queue solution doc.

## Risk Resolution
- **Risk tracked:** SQLite fan-out adequacy when `POST /events` inserts many delivery rows in one transaction
- **What actually happened:** Fan-out is atomic (single `db.commit()` after the loop over matching webhooks). The correctness risk is handled. The scalability concern (loading all active webhooks into memory for Python-side event filter) is a known limitation documented in the brainstorm.
- **Lesson:** SQLite fan-out is fine for small scale. At large scale (1000+ webhooks), replace the Python filter with a SQLite JSON function query or denormalize events into a separate `webhook_events` table with a proper index.

## Schema
```sql
webhooks(id, url, secret, events TEXT JSON, max_attempts, is_active, created_at)
deliveries(id, webhook_id, event_type, payload TEXT JSON, status,
           attempt_count, max_attempts, next_attempt_at,
           last_error, worker_id, claimed_at, created_at, completed_at)
```

## Status Machine
```
pending → delivering → delivered
                     → failed (attempt_count+1 >= max_attempts)
delivering → pending  (timeout: worker silent for 300s, retries remain)
delivering → failed   (timeout: worker silent, retries exhausted)
```
