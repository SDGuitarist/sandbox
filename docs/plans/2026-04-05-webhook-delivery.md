---
title: "Webhook Delivery System"
date: 2026-04-05
status: ready
brainstorm: "docs/brainstorms/2026-04-05-webhook-delivery.md"
feed_forward:
  risk: "SQLite fan-out adequacy when POST /events inserts many delivery rows in one transaction"
  verify_first: true
---

# Webhook Delivery System — Plan

## What exactly is changing?
A new Flask application will be created in `/workspace/webhook-delivery/`. It exposes 8 HTTP endpoints backed by a SQLite database. It is self-contained — no dependency on the job-queue service.

## What must NOT change?
- `/workspace/job-queue/` must not be modified.
- `/workspace/url-shortener/` must not be modified.
- No external dependencies beyond Flask and Python stdlib (uuid, sqlite3, json, hmac, hashlib, datetime).

## How will we know it worked?
1. `POST /webhooks` returns 201 with a webhook `id`.
2. `POST /events` with a matching event_type creates one delivery row per active matching webhook, returns count of deliveries created.
3. `POST /deliveries/claim` atomically returns the oldest delivery whose `next_attempt_at <= now` and sets it to `delivering`.
4. A second concurrent `POST /deliveries/claim` does NOT return the same delivery.
5. `POST /deliveries/<id>/complete` sets status to `delivered`.
6. `POST /deliveries/<id>/fail` with retries remaining schedules retry: `next_attempt_at = now + 10 * 2^attempt_count seconds`, increments `attempt_count`, resets to `pending`.
7. `POST /deliveries/<id>/fail` with no retries remaining sets status to `failed`.
8. `DELETE /webhooks/<id>` sets `is_active=0`; subsequent `POST /events` does NOT create deliveries for it.
9. `GET /webhooks/<id>/deliveries` returns delivery history ordered by `created_at DESC`.

## What is the most likely way this plan is wrong?
SQLite's `datetime('now', '+N seconds')` arithmetic in the `next_attempt_at` calculation may behave unexpectedly if the computed offset is fractional or very large. Will verify with explicit test of the backoff value after a fail call.

---

## File Structure

```
/workspace/webhook-delivery/
├── app.py           # Flask app + all routes
├── database.py      # SQLite connection (WAL + verify), schema, init
├── signing.py       # HMAC-SHA256 signature generation
└── requirements.txt # Flask only
```

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS webhooks (
    id         TEXT PRIMARY KEY,
    url        TEXT NOT NULL,
    secret     TEXT NOT NULL,
    events     TEXT NOT NULL,   -- JSON array of event type strings
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deliveries (
    id              TEXT PRIMARY KEY,
    webhook_id      TEXT NOT NULL REFERENCES webhooks(id),
    event_type      TEXT NOT NULL,
    payload         TEXT NOT NULL,   -- JSON
    status          TEXT NOT NULL DEFAULT 'pending',
    attempt_count   INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 5,
    next_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_error      TEXT,
    worker_id       TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_deliveries_status_next ON deliveries(status, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_deliveries_webhook ON deliveries(webhook_id, created_at);
```

Status values: `pending` | `delivering` | `delivered` | `failed`

## `database.py`

WAL + verify pattern from job-queue solution doc:
```python
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, timeout=10)
        result = g.db.execute('PRAGMA journal_mode=WAL').fetchone()
        if result[0] != 'wal':
            raise RuntimeError(f"SQLite WAL mode could not be enabled (got: {result[0]})")
        g.db.row_factory = sqlite3.Row
    return g.db
```

Schema init once at startup via `init_db(app)`.

## `signing.py`

```python
import hmac, hashlib, json

def sign_payload(secret: str, payload: dict) -> str:
    body = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"sha256={sig}"
```

## Endpoints (`app.py`)

### POST /webhooks
- Body: `{"url": "https://...", "secret": "...", "events": ["order.created", ...], "max_attempts": 5}`
- Validate: `url` required + must start with http/https; `secret` required; `events` must be non-empty list of strings; `max_attempts` optional int > 0 (default 5)
- Return 201: `{"id": "...", "url": "...", "events": [...], "is_active": true, "created_at": "..."}`

### GET /webhooks/<id>
- Return 200 with full webhook row (parse `events` JSON), 404 if not found

### DELETE /webhooks/<id>
- Set `is_active=0` — soft delete
- Return 200: `{"id": "...", "is_active": false}`

### POST /events
- Body: `{"event_type": "order.created", "payload": {...}}`
- Both fields required
- Query: find all active webhooks where `events` JSON contains `event_type`:
  ```sql
  SELECT * FROM webhooks WHERE is_active=1 AND json_type(events) IS NOT NULL
  ```
  Then filter in Python: `event_type in json.loads(row['events'])`
- Insert one delivery row per matching webhook in a single transaction
- Return 200: `{"event_type": "...", "deliveries_created": N, "delivery_ids": [...]}`

### POST /deliveries/claim
- Body: `{"worker_id": "..."}` (optional — generate UUID if missing)
- Step 1: Expire timed-out `delivering` jobs — reset to `pending` if attempts remain, else `failed`:
  ```sql
  UPDATE deliveries SET
      status = CASE WHEN attempt_count < max_attempts THEN 'pending' ELSE 'failed' END,
      next_attempt_at = CASE WHEN attempt_count < max_attempts
          THEN datetime('now', '+' || CAST(10 * (1 << attempt_count) AS TEXT) || ' seconds')
          ELSE next_attempt_at END
  WHERE status = 'delivering'
    AND CAST((julianday('now') - julianday(next_attempt_at)) * 86400 AS INTEGER) >= 300
  ```
  (300s = 5 min hard timeout for a delivery worker)
- Step 2: Claim oldest due delivery atomically:
  ```sql
  -- Find ID first
  SELECT id FROM deliveries WHERE status='pending' AND next_attempt_at <= datetime('now')
  ORDER BY next_attempt_at ASC LIMIT 1
  -- Then UPDATE WHERE id=? AND status='pending'
  UPDATE deliveries SET status='delivering', worker_id=?
  WHERE id=? AND status='pending'
  ```
- Return 200 with full delivery row; 204 if none available

### POST /deliveries/<id>/complete
- Validate `status='delivering'`, else 409
- Set `status='delivered'`, `completed_at=now`
- Return 200

### POST /deliveries/<id>/fail
- Body: `{"error": "..."}` (optional)
- Validate `status='delivering'`, else 409
- Compute next_attempt_at: `datetime('now', '+' || CAST(10 * (1 << attempt_count) AS TEXT) || ' seconds')`
- If `attempt_count < max_attempts`: increment `attempt_count`, reset to `pending`, set `next_attempt_at`, store `last_error`
- If `attempt_count >= max_attempts`: set `failed`, store `last_error`, set `completed_at`
- Return 200

### GET /webhooks/<id>/deliveries
- Return all deliveries for webhook ordered by `created_at DESC`
- Return 200 with list, 404 if webhook not found

## Implementation Order
1. `requirements.txt`
2. `signing.py` — pure function, no deps
3. `database.py` — get_db, close_db, init_db, schema
4. `app.py` — all routes + error handlers

## Feed-Forward
- **Hardest decision:** Fan-out in `POST /events` — single transaction inserting N delivery rows. Acceptable at small scale; document as a known limitation.
- **Rejected alternatives:** Calling the job-queue API over HTTP (no scheduled delay support), shared SQLite file (tight coupling), background reaper thread for timeouts (added complexity).
- **Least confident:** The SQLite `datetime('now', '+N seconds')` expression inside a CASE — will test explicitly that backoff values are stored and filtered correctly.
