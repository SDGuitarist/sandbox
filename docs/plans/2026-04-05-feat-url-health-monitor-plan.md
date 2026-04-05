---
title: "URL Health Monitor"
type: feat
status: active
date: 2026-04-05
origin: docs/brainstorms/2026-04-05-url-health-monitor.md
feed_forward:
  risk: "Whether `requests` library is available in the environment, and whether outbound HTTP from the container will succeed. Need to verify before writing worker logic."
  verify_first: true
---

# feat: URL Health Monitor

## Enhancement Summary

**Deepened on:** 2026-04-05
**Research agents used:** solution-doc-searcher (job-queue, task-scheduler, webhook-delivery patterns)

### Key Corrections From Research
- Atomic claim: SELECT id → UPDATE WHERE id AND status='pending' → check rowcount → fetch by id (NOT by worker_id)
- Use `claimed_at` as timeout anchor (not scheduled time)
- Compute `next_run_at` for scheduler INSIDE BEGIN IMMEDIATE
- WAL + busy_timeout=5000ms on every connection
- requests library available, outbound HTTP confirmed working

## What Must Not Change

- Existing projects (task_scheduler/, job-queue/, webhook-delivery/, api-key-manager/, url-shortener/) — no modifications
- url_health_monitor/ must be completely self-contained with its own SQLite DB
- Atomic claim pattern must not be simplified away

## Prior Phase Risk

> "Whether `requests` library is available in the environment, and whether outbound HTTP from the container will succeed."

**Response:** Verified before plan was finalized — `pip install requests` succeeded, `requests.get('http://httpbin.org/get', timeout=5)` returned 200. Risk resolved. Workers can use `requests` for HTTP checks.

## Smallest Safe Plan

### Phase 1: Schema + DB layer
**Files:** `url_health_monitor/schema.sql`, `url_health_monitor/db.py`
**Shape:**
- `monitored_urls`: id, url, name, check_interval_seconds (default 300), failure_threshold (default 1), timeout_seconds (default 10), current_status (healthy/degraded/unknown), last_checked_at, created_at
- `check_jobs`: id, url_id, status (pending/running/completed/failed), created_at, claimed_at, worker_id, completed_at
- `check_results`: id, job_id, url_id, http_status_code, response_time_ms, error_message, checked_at
- db.py: `get_connection()` with WAL + busy_timeout=5000ms; `init_db()`
- Index: `(status, created_at)` on check_jobs; `(url_id, checked_at DESC)` on check_results
**Gate:** `init_db()` runs without error; all tables and indexes exist

### Phase 2: URL registry API (Flask)
**Files:** `url_health_monitor/app.py`, `url_health_monitor/routes.py`
**Shape:**
- `POST /urls` — register URL with name, optional check_interval_seconds, failure_threshold, timeout_seconds; validate URL scheme (http/https); return 201
- `GET /urls` — list all monitored URLs with current_status
- `GET /urls/<id>` — get URL details + last 10 check_results
- `DELETE /urls/<id>` — soft-delete (set status='deleted', stop scheduling)
- `GET /alerts` — return URLs where current_status='degraded', with last check result
**Gate:** All endpoints return correct JSON; invalid URL scheme returns 400

### Phase 3: Scheduler process
**Files:** `url_health_monitor/scheduler.py`
**Shape:**
- Poll every 10 seconds
- For each active URL where `last_checked_at IS NULL OR last_checked_at <= datetime('now', -check_interval_seconds || ' seconds')`: enqueue a check_job if no pending/running job exists for that URL
- Insert check_job with status='pending'
- Use WAL connection; handle OperationalError per-URL with continue
**Gate:** After waiting check_interval_seconds, a new check_job row appears for each active URL

### Phase 4: Worker process
**Files:** `url_health_monitor/worker.py`
**Shape:**
- Poll every 2 seconds for pending check_jobs
- Atomic claim: `UPDATE check_jobs SET status='running', claimed_at=now, worker_id=? WHERE id=? AND status='pending'` → rowcount check
- Fetch claimed job + url row
- Perform `requests.get(url, timeout=timeout_seconds)` with try/except
- Insert check_result row (http_status_code, response_time_ms, error_message)
- Update check_job status → 'completed' or 'failed'
- Update monitored_urls.current_status using this exact logic:
  ```sql
  SELECT status FROM check_results
  WHERE url_id = ? ORDER BY checked_at DESC LIMIT <failure_threshold>
  ```
  Rules:
  - If fewer than `failure_threshold` results exist → set current_status='unknown' (not enough data)
  - If ALL of the last N results have error_message IS NOT NULL (HTTP error or exception) → set 'degraded'
  - If ANY of the last N results succeeded (error_message IS NULL) → set 'healthy'
  - This means ONE success after N failures flips degraded→healthy immediately
- Timeout recovery: reset running→pending for jobs where `claimed_at < datetime('now', '-120 seconds')`
**Gate:** After running worker with a registered URL, check_results row exists; current_status updates correctly

### Phase 5: Wire up + README
**Files:** `url_health_monitor/requirements.txt`, `url_health_monitor/README.md`
**Shape:**
- requirements.txt: flask, requests
- README: setup, curl examples, how to start all three processes
**Gate:** Fresh checkout can register a URL and see it being checked

## Rejected Options

- **Embedded Flask thread:** Multi-worker duplicate checks — same reason as task-scheduler rejection
- **Timer-loop worker without queue:** No history, no retry, no concurrency safety — explicit requirements
- **Dynamic degraded query (no stateful field):** Slow alert endpoint requiring subquery on every request; stateful `current_status` is simpler and faster

## Risks And Unknowns

1. **HTTP timeout behavior:** `requests.get(timeout=10)` raises `requests.exceptions.Timeout` — must be caught separately from other exceptions
2. **SSL errors:** `requests.get` raises `SSLError` for invalid certs — should record as failed check, not crash worker
3. **Redirect following:** `requests` follows redirects by default — this is probably correct for health monitoring but worth noting
4. **Worker timeout recovery:** If a worker crashes mid-check, the job stays 'running' forever. Reset running→pending for jobs where `claimed_at < now - 120s`
5. **check_results growth:** No pruning. Acceptable for this scope.

## Most Likely Way This Plan Is Wrong

The `current_status` update after each check queries the last N results for that URL. Edge cases that must be handled:
1. **Fewer than N results** (first few checks): must return 'unknown', not 'healthy' or 'degraded'
2. **Recovery rule**: ONE success after N failures → 'healthy' immediately (one success in last N = not all failed)
3. **SQL ordering must be DESC**: `ORDER BY checked_at DESC LIMIT failure_threshold` — wrong order = checking oldest instead of newest results

If any of these three edge cases are implemented incorrectly, the alert endpoint will return wrong data.

## Scope Creep Check

All items in plan trace to brainstorm. WAL verification added (addresses feed_forward risk). README added (necessary). No scope creep.

## Acceptance Criteria

- `POST /urls` with valid http URL returns 201 with id
- `POST /urls` with non-http/https URL returns 400
- `GET /urls` returns array of all non-deleted URLs with current_status
- `GET /urls/<id>` returns URL + last 10 check_results
- `DELETE /urls/<id>` soft-deletes; deleted URL no longer appears in GET /urls
- After worker runs: check_results row exists with http_status_code and response_time_ms
- After `failure_threshold` consecutive failures: current_status transitions to 'degraded'
- After a successful check: current_status transitions back to 'healthy'
- `GET /alerts` returns only URLs with current_status='degraded'
- `GET /alerts` returns empty array when no URLs are degraded

## Tests Or Checks

```bash
cd url_health_monitor
python -c "from db import init_db; init_db()"
flask run --port 5006 &

# Register a URL
curl -s -X POST http://localhost:5006/urls \
  -H "Content-Type: application/json" \
  -d '{"url": "http://httpbin.org/get", "name": "httpbin"}' | python -m json.tool

# Invalid scheme
curl -s -X POST http://localhost:5006/urls \
  -H "Content-Type: application/json" \
  -d '{"url": "ftp://example.com", "name": "ftp"}' | python -m json.tool
# Expect 400

# Check dashboard
curl -s http://localhost:5006/urls | python -m json.tool
curl -s http://localhost:5006/alerts | python -m json.tool

# Start worker and wait
python worker.py &
sleep 5
curl -s http://localhost:5006/urls/1 | python -m json.tool
# Expect check_results populated
```

## Rollback Plan

All code in `url_health_monitor/` — isolated from all other projects. To undo:
1. `rm -rf url_health_monitor/` removes all new code
2. No migrations to existing DBs — uses its own `health_monitor.db`

## Claude Code Handoff Prompt

```text
Read docs/plans/2026-04-05-feat-url-health-monitor-plan.md.

PREREQUISITE: requests library confirmed available; outbound HTTP confirmed working.

Repos and files in scope:
- url_health_monitor/db.py
- url_health_monitor/schema.sql
- url_health_monitor/app.py
- url_health_monitor/routes.py
- url_health_monitor/scheduler.py
- url_health_monitor/worker.py
- url_health_monitor/requirements.txt
- url_health_monitor/README.md

Scope boundaries:
- DO NOT modify any files outside url_health_monitor/
- DO NOT use APScheduler, Celery, or background threads
- DO NOT use a DB other than SQLite

Acceptance criteria:
- POST /urls with valid http URL => 201
- POST /urls with non-http URL => 400
- GET /urls returns all non-deleted URLs
- GET /alerts returns only degraded URLs
- Worker updates current_status based on failure_threshold

Stop conditions:
- Stop if outbound HTTP is blocked (test with requests.get before worker code)
- Stop if any file outside url_health_monitor/ would need to change
```

## Sources

- Brainstorm: docs/brainstorms/2026-04-05-url-health-monitor.md

## Feed-Forward

- **Hardest decision:** Stateful `current_status` vs dynamic query for alert endpoint. Stateful wins — O(1) alert query vs O(N) subquery at scale; state machine is simple enough.
- **Rejected alternatives:** Background Flask thread, timer-loop without queue, dynamic degraded query
- **Least confident:** Whether the `current_status` update logic (query last N results, all-failed = degraded) handles edge cases correctly — specifically what happens on the very first check (no prior results), and transitions from degraded back to healthy.
