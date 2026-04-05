---
title: "Job Queue System with Flask + SQLite"
date: 2026-04-05
status: complete
origin: "conversation"
---

# Job Queue System with Flask + SQLite — Brainstorm

## Problem
Developers need a way to submit jobs for asynchronous execution, have workers claim and execute them, and track job status + results. The system must handle retries when jobs fail and timeouts when workers go silent.

## Context
- Stack: Python + Flask + SQLite (explicitly required)
- Workers poll the API — no message broker (Redis, RabbitMQ) required
- SQLite is single-file, no separate server — good for small-scale, embedded deployments
- Prior art in this workspace: Flask+SQLite URL shortener — reuse WAL mode + secrets patterns
- Key challenge: multiple workers polling concurrently must claim jobs atomically (no double-claim)

## Options

### Option A: Optimistic locking with UPDATE ... WHERE status='pending' LIMIT 1
Workers issue: `UPDATE jobs SET status='running', worker_id=?, started_at=? WHERE id=(SELECT id FROM jobs WHERE status='pending' ORDER BY created_at LIMIT 1)`
Then check rowcount — if 0, no job available; if 1, claimed it.
- Pros: Single round-trip, atomic in SQLite (serialized writes), no extra claimed_by column confusion
- Cons: SQLite doesn't support `UPDATE ... LIMIT` in all versions — needs subquery form

### Option B: Pessimistic locking with a `claimed_at` transition field
Add `claimed_at` timestamp. Worker claims by setting `status='claimed'`, then starts running.
- Pros: More states visible, easier debugging
- Cons: Two-phase claim adds complexity; extra state machine transitions

### Option C: Separate queue table + job table
Queue holds pending job IDs; workers pop from queue, job table holds status/results.
- Pros: Clean separation of concerns
- Cons: Two tables for what is fundamentally one entity; unnecessary complexity for SQLite scale

## Tradeoffs
- **Simplicity vs. observability:** Option A is cleanest, Option B gives more debuggable states
- **Atomicity:** All options are atomic in SQLite because writes serialize — the race condition is actually safe here (unlike PostgreSQL where concurrent transactions can conflict)
- **Timeout detection:** Needs a background mechanism or API-side detection. Worker calls `POST /jobs/<id>/heartbeat` or timeout is detected at claim time by checking `started_at + timeout_seconds < now` for 'running' jobs — reclaim them

## Decision
**Option A** — single `UPDATE ... WHERE id=(SELECT ...)` for atomic claim. Status machine:
`pending → running → completed | failed`

Timeout recovery: when a worker polls, also scan for `running` jobs where `started_at + timeout_seconds < now` and reset them to `pending` (incrementing `retry_count`). If `retry_count >= max_retries`, set to `failed`.

Job schema:
```
jobs(
  id TEXT PRIMARY KEY,           -- UUID
  payload TEXT NOT NULL,         -- JSON string
  status TEXT NOT NULL DEFAULT 'pending',  -- pending|running|completed|failed
  result TEXT,                   -- JSON string, null until complete
  error TEXT,                    -- error message on failure
  retry_count INTEGER DEFAULT 0,
  max_retries INTEGER DEFAULT 3,
  timeout_seconds INTEGER DEFAULT 30,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  worker_id TEXT                 -- which worker is running it
)
```

API endpoints:
- `POST /jobs` — submit a job (payload, max_retries, timeout_seconds)
- `GET /jobs/<id>` — get job status + result
- `POST /jobs/claim` — worker polls: atomically claims next pending job (also expires timed-out running jobs)
- `POST /jobs/<id>/complete` — worker reports success + result
- `POST /jobs/<id>/fail` — worker reports failure (triggers retry or final failure)

## Open Questions
- Should `POST /jobs/claim` be idempotent with a `worker_id` parameter? Yes — worker sends its ID, stored in the job row for debugging.
- Should there be a `GET /jobs` list endpoint? Out of scope for this spec — keep it minimal.
- What's the job ID format? UUID4 (use `import uuid; str(uuid.uuid4())`).

## Feed-Forward
- **Hardest decision:** Timeout detection at claim time vs. a separate background reaper process. Chose claim-time detection — simpler, no background thread, but means timed-out jobs won't be recovered until the next worker poll.
- **Rejected alternatives:** Separate queue + jobs tables (Option C — unnecessary complexity), heartbeat endpoint (adds worker complexity), message brokers (out of scope).
- **Least confident:** Whether SQLite's serialized writes truly prevent double-claim under concurrent workers, or if connection-level isolation + WAL mode introduces a window where two workers read the same `pending` job ID before either commits. Need to verify with explicit WAL + timeout=10 settings (same as URL shortener pattern).
