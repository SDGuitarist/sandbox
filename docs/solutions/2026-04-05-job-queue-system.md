---
title: "Flask Job Queue System with SQLite"
date: 2026-04-05
tags: [flask, sqlite, job-queue, background-workers, retries, timeouts, python]
---

# Flask Job Queue System — Solution Doc

## Problem Solved
Built a Flask REST API job queue backed by SQLite. Workers poll `POST /jobs/claim`, execute jobs, and report results via `POST /jobs/<id>/complete` or `POST /jobs/<id>/fail`. Supports configurable retries and timeouts with recovery built into the claim step.

## Key Decisions

### Atomic job claim: SELECT then UPDATE WHERE id=? AND status='pending'
Do NOT fetch the claimed row by worker_id after an UPDATE. Instead:
1. `SELECT id FROM jobs WHERE status='pending' ORDER BY created_at ASC LIMIT 1`
2. `UPDATE jobs SET status='running', worker_id=? WHERE id=? AND status='pending'`
3. Check `cursor.rowcount` — 0 means another worker won; fetch by `id` if 1.

```python
pending = db.execute("SELECT id FROM jobs WHERE status='pending' ORDER BY created_at ASC LIMIT 1").fetchone()
if pending is None:
    return '', 204
cursor = db.execute("UPDATE jobs SET status='running', ... WHERE id=? AND status='pending'", (job_id_to_claim,))
if cursor.rowcount == 0:
    return '', 204  # Another worker beat us
row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id_to_claim,)).fetchone()
```

**Why:** Fetching by `worker_id` after the UPDATE can return the wrong row if two workers share the same ID or a worker has multiple in-flight connections. Always fetch by the specific `id` you claimed.

### Timeout detection at claim time (not a background reaper)
Reset timed-out `running` jobs to `pending` at the top of every `claim_job` call:
```sql
UPDATE jobs SET
    status = CASE WHEN retry_count < max_retries THEN 'pending' ELSE 'failed' END,
    retry_count = CASE WHEN retry_count < max_retries THEN retry_count + 1 ELSE retry_count END,
    started_at = NULL, completed_at = NULL, worker_id = NULL,
    error = CASE WHEN retry_count < max_retries THEN 'job timed out' ELSE error END
WHERE status = 'running'
  AND started_at IS NOT NULL
  AND CAST((julianday('now') - julianday(started_at)) * 86400 AS INTEGER) >= timeout_seconds
```
**Trade-off:** Timed-out jobs only recover when the next worker polls. No background thread needed.

### Generate worker_id server-side if not provided
```python
worker_id = data.get('worker_id') or str(uuid.uuid4())
```
Never use empty string as worker_id — it makes debug queries useless and the row-fetch ambiguous.

### WAL mode must be verified, not just set
```python
result = g.db.execute('PRAGMA journal_mode=WAL').fetchone()
if result[0] != 'wal':
    raise RuntimeError(f"SQLite WAL mode could not be enabled (got: {result[0]})")
```
SQLite silently falls back to DELETE journal mode on some filesystems (NFS, some Docker volumes). The entire concurrency model depends on WAL — verify it.

### Index on (status, created_at) for claim and timeout queries
```sql
CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);
```
Both the claim query (`WHERE status='pending' ORDER BY created_at`) and timeout query (`WHERE status='running'`) need this to avoid full table scans.

### Input validation on numeric fields
```python
try:
    max_retries = int(data.get('max_retries', 3))
    timeout_seconds = int(data.get('timeout_seconds', 30))
except (ValueError, TypeError):
    return jsonify({'error': '...'}), 400
if max_retries < 0: return 400
if timeout_seconds <= 0: return 400
```
`max_retries=-1` silently breaks the retry CASE expression, causing all timed-out jobs to immediately fail. Always bounds-check.

### `complete` endpoint requires `result` field explicitly
Return 400 if `result` is missing from the complete body. `json.dumps(None)` stores `"null"` which is truthy and confusing — require explicit intent.

## Risk Resolution
- **Risk tracked:** SQLite serialized writes preventing double-claim under WAL mode with concurrent workers
- **What actually happened:** The UPDATE itself is atomic and correct — SQLite write serialization prevents two workers from claiming the same job via the UPDATE. The real risk was in the read-after-write: fetching the claimed row by `worker_id` (not `id`) could return the wrong job row if worker IDs collide.
- **Lesson:** "Atomic UPDATE" and "safe read-after-write" are separate problems. Verify both. Always fetch by the specific ID you just wrote, never by a secondary field.

## Status Machine
```
pending → running → completed
                 → failed (retries exhausted)
running → pending (timeout recovery, retries remain)
running → failed  (timeout recovery, retries exhausted)
```

## API Surface
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs` | POST | Submit a job |
| `/jobs/<id>` | GET | Get job status + result |
| `/jobs/claim` | POST | Worker claims next pending job |
| `/jobs/<id>/complete` | POST | Worker reports success |
| `/jobs/<id>/fail` | POST | Worker reports failure (retries or terminates) |
