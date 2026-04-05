---
title: "Distributed Task Scheduler"
type: feat
status: active
date: 2026-04-05
origin: docs/brainstorms/2026-04-05-distributed-task-scheduler.md
feed_forward:
  risk: "SQLite WAL mode behavior under concurrent writes from scheduler process + Flask workers simultaneously. Need to verify WAL is enabled and that the job_runs insert is truly atomic under load."
  verify_first: true
---

# feat: Distributed Task Scheduler

## Enhancement Summary

**Deepened on:** 2026-04-05
**Research agents used:** solution-doc-searcher (job-queue atomics, webhook next_run_at patterns)

### Key Corrections From Research
- Atomic claim must use SELECT id → UPDATE WHERE id AND status='pending' → rowcount check (NOT select-by-worker-id pattern)
- Use `claimed_at` as timeout anchor, not scheduling time
- Index must be on `(status, next_run_at)` for efficient claim queries
- WAL mode must be enabled explicitly at connection time

## What Must Not Change

- Existing `job-queue/` project files (no modifications to prior projects)
- Existing `webhook-delivery/` project files
- SQLite file must live at `task_scheduler/scheduler.db` (isolated from other projects)
- The atomic claim pattern from job-queue solution doc must not be simplified away
- Flask app must remain importable standalone (no mandatory scheduler process to import)

## Prior Phase Risk

> "SQLite WAL mode behavior under concurrent writes from scheduler process + Flask workers simultaneously. Need to verify WAL is enabled and that the job_runs insert is truly atomic under load."

**Response:** Phase 1 task is to verify WAL mode works correctly. Every SQLite connection (both Flask app and scheduler.py) will call `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` immediately after connecting. The busy_timeout ensures concurrent writes retry rather than immediately failing. This is validated before any other code runs.

## Smallest Safe Plan

### Phase 1: Database schema + WAL verification
**Files:** `task_scheduler/db.py`, `task_scheduler/schema.sql`
**Shape:**
- `schedules` table: id, name, cron_expr, payload (JSON text), status (active/paused/deleted), created_at, next_run_at
- `job_runs` table: id, schedule_id, status (pending/running/completed/failed), payload (JSON text), created_at, claimed_at, completed_at, result (JSON text)
- `db.py`: `get_connection()` that enables WAL + busy_timeout on every new connection; `init_db()` to create tables
- Verify WAL: write a small smoke test that opens two connections simultaneously and does concurrent inserts
**Gate:** WAL smoke test passes; both tables exist with correct columns

### Phase 2: Schedule submission API (Flask)
**Files:** `task_scheduler/app.py`, `task_scheduler/routes.py`
**Shape:**
- `POST /schedules` — create schedule, compute initial next_run_at from cron_expr using croniter, insert with status='active'
- `GET /schedules` — list all schedules
- `GET /schedules/<id>` — get single schedule with its recent job_runs
- `PATCH /schedules/<id>` — update status (pause/resume/delete)
- Validate cron_expr on submit (croniter raises on invalid)
- Return 400 with error message on invalid cron
**Gate:** All 4 endpoints return expected JSON; invalid cron returns 400

### Phase 3: Scheduler process
**Files:** `task_scheduler/scheduler.py`
**Shape:**
- Poll loop every 10 seconds
- Query: `SELECT id FROM schedules WHERE status='active' AND next_run_at <= datetime('now')`
- For each due schedule: atomic claim via `UPDATE schedules SET next_run_at=[next after now] WHERE id=? AND next_run_at <= datetime('now')` + rowcount check (skip if rowcount=0 = another process beat us)
- Insert job_run with status='pending', payload copied from schedule
- Use croniter to compute next_run_at after firing
- Graceful shutdown on SIGTERM/SIGINT
**Gate:** Manually verify a schedule fires exactly once when due; no duplicates under 2 simultaneous scheduler processes

### Phase 4: Dashboard endpoint
**Files:** `task_scheduler/routes.py` (add endpoint)
**Shape:**
- `GET /dashboard` — returns JSON with three sections:
  - `upcoming`: next 10 fires across all active schedules (sorted by next_run_at)
  - `overdue`: schedules where next_run_at < now AND status='active' AND no pending/running job_run exists
  - `completed`: last 20 completed job_runs (sorted by completed_at desc)
**Gate:** Dashboard returns all three sections; overdue correctly identifies missed schedules

### Phase 5: Wire up + README
**Files:** `task_scheduler/README.md`, `task_scheduler/requirements.txt`
**Shape:**
- requirements.txt: flask, croniter
- README: how to init DB, start Flask, start scheduler, curl examples
**Gate:** Fresh checkout can follow README to get both processes running

## Rejected Options

- **Embedded Flask thread:** SQLite + multiple gunicorn workers = multiple scheduler threads = duplicate job fires. Thread safety is the deciding factor.
- **APScheduler/Celery Beat:** Heavyweight dependencies, stores its own state, fights with our schema. Doesn't match the learning goals or the existing job-queue pattern.

## Risks And Unknowns

1. **croniter version compatibility:** croniter API changed between v1 and v2. Pin version in requirements.txt.
2. **SQLite busy under load:** If Flask is doing many writes simultaneously with scheduler, busy_timeout=5000ms may still occasionally fail. Acceptable for this project; document it.
3. **Clock skew:** If scheduler process clock drifts, next_run_at comparisons could misfire. Using `datetime('now')` in SQLite (server clock) mitigates this.
4. **"Overdue" definition:** A schedule is overdue if next_run_at < now AND no pending/running job_run exists. If a job_run is pending but hasn't been worked, we don't double-count it.

## Most Likely Way This Plan Is Wrong

The atomic claim in Phase 3 uses `UPDATE schedules SET next_run_at=...` as the claim mechanism. This means `next_run_at` is advanced before the job_run is inserted. If the scheduler crashes between those two steps, the schedule silently skips a run with no job_run record. Fix: wrap both operations in a single transaction (`BEGIN IMMEDIATE`).

## Scope Creep Check

Compare against brainstorm: `docs/brainstorms/2026-04-05-distributed-task-scheduler.md`
- All three subsystems from brainstorm are covered: submit API, scheduler loop, dashboard
- WAL verification added (not in brainstorm, but required to address feed_forward risk)
- README added (not in brainstorm, but necessary for usability — not a new feature)
- No scope creep identified

## Acceptance Criteria

- `POST /schedules` with valid cron_expr returns 201 with schedule id and next_run_at
- `POST /schedules` with invalid cron_expr returns 400 with error message
- `GET /schedules` returns array of all schedules
- `PATCH /schedules/<id>` with `{"status": "paused"}` stops scheduler from firing that schedule
- A schedule with `next_run_at <= now` produces exactly one job_run with status='pending' per fire
- Two simultaneous scheduler.py processes do NOT produce duplicate job_runs for the same fire
- `GET /dashboard` returns JSON with `upcoming`, `overdue`, and `completed` keys
- `upcoming` contains at most 10 entries sorted by next_run_at ascending
- `completed` contains at most 20 entries sorted by completed_at descending
- `overdue` correctly identifies schedules where next_run_at is in the past with no pending job

## Tests Or Checks

```bash
# 1. Init DB and start Flask
cd task_scheduler
python -c "from db import init_db; init_db()"
flask run --port 5005 &

# 2. Submit a schedule (every minute)
curl -s -X POST http://localhost:5005/schedules \
  -H "Content-Type: application/json" \
  -d '{"name": "test-job", "cron_expr": "* * * * *", "payload": {"action": "ping"}}' | python -m json.tool

# 3. Check dashboard
curl -s http://localhost:5005/dashboard | python -m json.tool

# 4. Start scheduler and wait 65 seconds
python scheduler.py &
sleep 65

# 5. Verify job_run was created
curl -s http://localhost:5005/schedules/1 | python -m json.tool

# 6. Test invalid cron
curl -s -X POST http://localhost:5005/schedules \
  -H "Content-Type: application/json" \
  -d '{"name": "bad", "cron_expr": "not-a-cron", "payload": {}}' | python -m json.tool
# Expect: 400

# 7. Test duplicate-fire prevention
python scheduler.py &  # second instance
sleep 65
# Count job_runs for same schedule — should still be 1 per minute, not 2
```

## Rollback Plan

All new code is in `task_scheduler/` directory, isolated from other projects. To undo:
1. `rm -rf task_scheduler/` removes all new code
2. No migrations to existing DBs — task_scheduler uses its own `scheduler.db`
3. No changes to existing Flask apps or job-queue projects
4. If DB is corrupted: `rm task_scheduler/scheduler.db && python -c "from db import init_db; init_db()"`

## Claude Code Handoff Prompt

```text
Read docs/plans/2026-04-05-feat-distributed-task-scheduler-plan.md.

PREREQUISITE: Verify SQLite WAL mode works with concurrent connections before writing any other code (Phase 1 gate).

Repos and files in scope:
- task_scheduler/db.py (new)
- task_scheduler/schema.sql (new)
- task_scheduler/app.py (new)
- task_scheduler/routes.py (new)
- task_scheduler/scheduler.py (new)
- task_scheduler/requirements.txt (new)
- task_scheduler/README.md (new)

Scope boundaries:
- DO NOT modify any files outside task_scheduler/
- DO NOT modify job-queue/, webhook-delivery/, or any other existing project
- DO NOT use APScheduler, Celery, or any task queue library — use raw SQLite + croniter only
- DO NOT embed a background thread in Flask — scheduler must be a separate process

Key corrections from plan review:
[To be filled after Codex review]

Acceptance criteria:
- POST /schedules with valid cron returns 201 with next_run_at
- POST /schedules with invalid cron returns 400
- GET /schedules returns array
- PATCH /schedules/<id> pauses/resumes schedule
- Exactly one job_run per schedule fire (no duplicates under concurrent schedulers)
- GET /dashboard returns upcoming (10), overdue, completed (20) sections

Required checks:
- WAL smoke test passes (two concurrent connections, no SQLITE_BUSY)
- Manual duplicate-fire test: run two scheduler.py instances, verify no duplicate job_runs

Stop conditions:
- Stop if croniter import fails — check requirements.txt and pip install
- Stop if WAL smoke test fails — investigate before proceeding to Phase 2
- Stop if any file outside task_scheduler/ would need to be modified
```

## Sources

- Brainstorm: docs/brainstorms/2026-04-05-distributed-task-scheduler.md
- Solution doc (job queue atomics): docs/solutions/2026-04-05-job-queue-system.md
- Solution doc (next_run_at scheduling): docs/solutions/2026-04-05-webhook-delivery-system.md

## Feed-Forward

- **Hardest decision:** Atomic claim mechanism — advancing next_run_at before inserting job_run creates a crash window. Solved by wrapping both in BEGIN IMMEDIATE transaction.
- **Rejected alternatives:** Embedded Flask thread (duplicate fires under gunicorn), APScheduler (opaque, fights our schema), back-filling missed runs (could flood queue after downtime — skip instead)
- **Least confident:** Whether `BEGIN IMMEDIATE` on SQLite is sufficient under high concurrency, or if the busy_timeout=5000ms will cause user-visible latency on the Flask API during scheduler bursts.
