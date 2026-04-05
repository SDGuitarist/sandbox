---
title: "Job Queue System with Flask + SQLite"
date: 2026-04-05
status: ready
brainstorm: "docs/brainstorms/2026-04-05-job-queue-system.md"
feed_forward:
  risk: "SQLite serialized writes truly prevent double-claim under concurrent workers with WAL mode"
  verify_first: true
---

# Job Queue System with Flask + SQLite — Plan

## What exactly is changing?
A new Flask application will be created in `/workspace/job-queue/`. It exposes 5 HTTP endpoints backed by a SQLite database. Workers are external processes that poll `POST /jobs/claim` and report results via `POST /jobs/<id>/complete` or `POST /jobs/<id>/fail`.

## What must NOT change?
- The existing `url-shortener/` project must not be touched.
- The existing `cli-todo-app` project must not be touched.
- No external dependencies beyond Flask and Python stdlib (uuid, sqlite3, json).

## How will we know it worked?
1. `POST /jobs` returns 201 with a job `id` and `status: pending`.
2. `POST /jobs/claim` returns the oldest pending job and sets its status to `running`.
3. A second concurrent `POST /jobs/claim` does NOT return the same job.
4. `POST /jobs/<id>/complete` sets status to `completed` and stores result.
5. `POST /jobs/<id>/fail` decrements retries: if retries remain, resets to `pending`; if exhausted, sets `failed`.
6. A job that has been `running` for longer than `timeout_seconds` is reclaimed as `pending` by the next `POST /jobs/claim` call.
7. `GET /jobs/<id>` returns current status, result, error, retry_count.

## What is the most likely way this plan is wrong?
The atomic claim via SQLite subquery UPDATE may behave differently under WAL mode with concurrent connections — SQLite's WAL allows concurrent readers but serializes writers. If two workers open connections simultaneously, the second UPDATE will either see the first's commit (correct) or block on the write lock and retry. With `timeout=10`, blocking is safe. The risk is low but worth explicit testing.

---

## File Structure

```
/workspace/job-queue/
├── app.py           # Flask app + all routes
├── database.py      # SQLite connection (WAL + timeout), schema init
├── requirements.txt # Flask only
```

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    payload         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    result          TEXT,
    error           TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    max_retries     INTEGER NOT NULL DEFAULT 3,
    timeout_seconds INTEGER NOT NULL DEFAULT 30,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    worker_id       TEXT
);
```

Status values: `pending` | `running` | `completed` | `failed`

## `database.py`

Same pattern as url-shortener — WAL mode + timeout=10:

```python
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, timeout=10)
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.row_factory = sqlite3.Row
    return g.db
```

Schema init called once at startup via `init_db(app)`.

## Endpoints (`app.py`)

### POST /jobs
- Body: `{"payload": {...}, "max_retries": 3, "timeout_seconds": 30}`
- `payload` is required (any JSON value); `max_retries` and `timeout_seconds` are optional with defaults
- Generate UUID4 job ID
- Insert with `status='pending'`
- Return 201: `{"id": "...", "status": "pending", "created_at": "..."}`

### GET /jobs/<id>
- Fetch job by ID
- Return 200 with all fields, 404 if not found

### POST /jobs/claim
- Body: `{"worker_id": "..."}` (optional but stored for debugging)
- Step 1: Expire timed-out running jobs — reset to pending if retries remain, else fail:
  ```sql
  UPDATE jobs SET
      status = CASE WHEN retry_count < max_retries THEN 'pending' ELSE 'failed' END,
      retry_count = CASE WHEN retry_count < max_retries THEN retry_count + 1 ELSE retry_count END,
      started_at = NULL, worker_id = NULL
  WHERE status = 'running'
    AND started_at IS NOT NULL
    AND CAST((julianday('now') - julianday(started_at)) * 86400 AS INTEGER) >= timeout_seconds
  ```
- Step 2: Claim oldest pending job atomically:
  ```sql
  UPDATE jobs SET status='running', started_at=CURRENT_TIMESTAMP, worker_id=?
  WHERE id = (SELECT id FROM jobs WHERE status='pending' ORDER BY created_at ASC LIMIT 1)
  ```
  Check `cursor.rowcount` — if 0, return 204 (no job available); if 1, fetch and return 200.
- Return 200: full job row; 204 if no pending jobs

### POST /jobs/<id>/complete
- Body: `{"result": {...}}` (any JSON value)
- Validate job exists and is `running`
- Set `status='completed'`, `result=json.dumps(body.result)`, `completed_at=now`
- Return 200: updated job

### POST /jobs/<id>/fail
- Body: `{"error": "..."}` (optional message)
- Validate job exists and is `running`
- If `retry_count < max_retries`: increment `retry_count`, reset to `pending`, clear `started_at`/`worker_id`
- If `retry_count >= max_retries`: set `status='failed'`, store `error`
- Return 200: updated job

## Error Handling
- 404 on unknown job ID
- 409 Conflict if `complete` or `fail` called on a job not in `running` state
- JSON error handlers for 404/405 (same pattern as url-shortener)

## Implementation Order
1. `requirements.txt`
2. `database.py` — get_db, close_db, init_db, schema
3. `app.py` — POST /jobs, GET /jobs/<id>, POST /jobs/claim, POST /jobs/<id>/complete, POST /jobs/<id>/fail + error handlers

## Feed-Forward
- **Hardest decision:** Timeout detection at claim time (not a background reaper) — simpler, no threads, but timed-out jobs only recover when next worker polls.
- **Rejected alternatives:** Heartbeat endpoint (worker complexity), separate queue table (unnecessary), message brokers (out of scope).
- **Least confident:** SQLite WAL + concurrent UPDATE atomicity — using `timeout=10` and verifying rowcount after UPDATE is the mitigation; will test with back-to-back claim calls.
