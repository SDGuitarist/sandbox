---
title: "Service Mesh Dashboard"
type: feat
status: active
date: 2026-04-05
origin: "docs/brainstorms/2026-04-05-service-mesh-dashboard.md"
feed_forward:
  risk: "SSRF check at registration time may not be sufficient — DNS rebinding can bypass hostname resolution checks. Document the gap; use allow_redirects=False in worker as second defense line."
  verify_first: true
---

# feat: Service Mesh Dashboard

## Enhancement Summary

**Deepened on:** 2026-04-05
**Research agents used:** solution-doc-searcher (5 prior solution docs)

### Key Corrections From Research
- SSRF requires TWO fixes: IP check at registration + `allow_redirects=False` in worker (from url-health-monitor)
- API key validation: salted SHA-256, prefix-based lookup, `hmac.compare_digest` (from api-key-manager)
- Atomic job claim: SELECT id → UPDATE WHERE id AND status='pending' → check rowcount (from job-queue)
- Cursor pagination: `events[limit-1]["id"]` not `events[limit]["id"]` (from audit-log)
- Scheduler `NOT EXISTS` check inside `BEGIN IMMEDIATE` (from url-health-monitor)
- `next_run_at` / `scheduled_at` computed inside the lock transaction (from task-scheduler)

## What Must Not Change

- The `events` table is append-only — no UPDATE or DELETE on events rows
- API key validation must use `hmac.compare_digest` (not `==`) for constant-time comparison
- Worker is a separate process, NOT a Flask background thread
- `get_db()` context manager semantics (WAL, row_factory, rollback on exception, explicit close)
- Test isolation — each test gets its own `tmp_path` DB + migrations dir
- SSRF protection must be applied at both registration time and worker request time

## Prior Phase Risk

> "SSRF check at registration time may not be sufficient — DNS rebinding can bypass hostname resolution checks."

**Response:** Add a verify-first test that confirms both SSRF layers work:
1. Registration of a URL resolving to 127.0.0.1 is rejected (layer 1)
2. Worker uses `allow_redirects=False` so redirect to 127.0.0.1 is also blocked (layer 2)
Document in code that DNS rebinding is a known gap for this MVP.

## Smallest Safe Plan

### Phase 1: DB layer + schema + verify-first SSRF test

**Files:** `dashboard/schema.sql`, `dashboard/db.py`, `tests/test_dashboard_ssrf.py`

**What to build:**
- `schema.sql`: 5 tables: `services`, `api_keys`, `health_results`, `health_jobs`, `events`
- `get_db(path, immediate)` context manager (WAL, row_factory, BEGIN IMMEDIATE)
- `init_db(path)` raw connection + executescript
- `dashboard/ssrf.py`: `validate_url(url)` — parse URL, resolve hostname, reject private/loopback/link-local IPs; raise `SSRFError` with message
- Verify-first test: private IP rejected at registration, `allow_redirects=False` in requests confirmed

**Gate:** Verify-first SSRF tests pass before Phase 2.

### Phase 2: Services + API keys CRUD

**Files:** `dashboard/services.py`, `dashboard/keys.py`, `tests/test_dashboard_services.py`, `tests/test_dashboard_keys.py`

**What to build:**
- `services.py`:
  - `create_service(conn, name, health_check_url, url=None, description=None)` → `{id, name, ...}`
  - `get_service(conn, service_id)` → dict or None
  - `list_services(conn)` → list
  - `delete_service(conn, service_id)` → bool
  - `get_dashboard(conn)` → list of services with latest health status (LEFT JOIN subquery)
- `keys.py`:
  - `create_key(conn, label, service_id=None)` → `{id, key (raw, shown once), prefix, label, ...}`
  - `validate_key(conn, raw_key)` → `{id, label, service_id}` or None (prefix lookup + hmac.compare_digest)
  - `revoke_key(conn, key_id)` → bool
  - `list_keys(conn, service_id=None)` → list (never includes key material)

### Phase 3: Health checking + job queue

**Files:** `dashboard/health.py`, `dashboard/jobs.py`, `dashboard/worker.py`, `tests/test_dashboard_health.py`

**What to build:**
- `health.py`:
  - `record_result(conn, service_id, status, status_code=None, response_time_ms=None, error_message=None)` → dict
  - `get_latest_status(conn, service_id)` → dict or None
  - `list_results(conn, service_id, limit=20)` → list
- `jobs.py`:
  - `enqueue_job(conn, service_id, scheduled_at=None)` → dict
  - `claim_job(conn, worker_id)` → dict or None (atomic SELECT+UPDATE)
  - `complete_job(conn, job_id, success=True)` → bool
  - `enqueue_pending_services(conn)` — INSERT for services with no pending/running job (inside BEGIN IMMEDIATE)
- `worker.py`: standalone script — poll `claim_job`, fetch URL, `requests.get(timeout=5, allow_redirects=False)`, record result, complete job, append event if status changed. Exit code 0 on clean stop.

### Phase 4: Event timeline + Flask routes + app

**Files:** `dashboard/events.py`, `dashboard/routes.py`, `dashboard/app.py`, `dashboard/auth.py`, `run_dashboard.py`, `tests/test_dashboard_routes.py`

**What to build:**
- `events.py`:
  - `append_event(conn, event_type, service_id=None, payload=None)` → dict
  - `list_events(conn, after_id=None, limit=20, service_id=None)` → `{events: [...], next_cursor: int|None}`
- `auth.py`:
  - `require_auth(f)` — decorator; reads `Authorization: Bearer <key>`, calls `validate_key`, returns 401 if invalid; injects `g.api_key` dict
- Routes (all under `/`):
  - `POST /services` — create service (validate SSRF, append event) [auth required]
  - `GET /services` — list services
  - `GET /services/<id>` — get service with health history
  - `DELETE /services/<id>` — delete service + append event [auth required]
  - `POST /services/<id>/check` — manually trigger health check job [auth required]
  - `GET /dashboard` — aggregate status (all services + latest health)
  - `POST /keys` — create API key [auth required]
  - `DELETE /keys/<id>` — revoke key [auth required]
  - `GET /events` — paginated event timeline (query: ?after=N&limit=20&service_id=X)

## Rejected Options

- Separate SQLite DBs per concern — Python-side JOINs, unnecessary complexity
- Monolithic `db.py` — hard to test subsystems independently
- Flask background thread for worker — gunicorn multi-worker fires N times; separate process is correct
- Unsalted SHA-256 for keys — rainbow table vulnerable

## Risks And Unknowns

1. SSRF DNS rebinding gap — documented, both layers implemented, accepted for MVP
2. `requests` library availability — confirmed available in prior cycles
3. Worker process management — caller must start/stop separately; no supervisor in this service
4. Key display-once semantics — raw key shown in `POST /keys` response only; test that GET endpoints never expose key material

## Most Likely Way This Plan Is Wrong

The `get_dashboard` aggregate query (LEFT JOIN with correlated subquery for latest health result) may be slow for many services. For this MVP with SQLite and O(100) services it's acceptable. If performance becomes an issue, add a `current_status` column to `services` updated on each health record.

## Scope Creep Check

Compared to brainstorm: everything matches. Not adding:
- Webhook alerts — deferred
- UI / HTML rendering — deferred
- Rate limiting — deferred
- Multi-tenant isolation — deferred

## Acceptance Criteria

- [ ] `POST /services` creates a service, validates SSRF, appends registration event
- [ ] `POST /services` with private IP health_check_url returns 422
- [ ] `GET /dashboard` returns all services with latest health status (null if never checked)
- [ ] `POST /keys` returns key material once; `GET /services` never exposes key material
- [ ] `validate_key` returns None for revoked or nonexistent keys
- [ ] `claim_job` is atomic — concurrent claims don't double-assign the same job
- [ ] Worker records result, appends event on status change, marks job done/failed
- [ ] `GET /events` returns cursor-paginated results; `next_cursor` is correct
- [ ] All mutating routes return 401 without valid API key
- [ ] `DELETE /services/<id>` cascades to health_results, health_jobs, events (service_id FK)
- [ ] Manually triggered `POST /services/<id>/check` enqueues a job and returns 202

## Tests Or Checks

```bash
pytest tests/test_dashboard_ssrf.py -v        # verify-first gate
pytest tests/test_dashboard_services.py -v
pytest tests/test_dashboard_keys.py -v
pytest tests/test_dashboard_health.py -v
pytest tests/test_dashboard_routes.py -v
pytest tests/ -k dashboard -v                  # full suite
```

## Rollback Plan

All new files under `dashboard/`. No existing files modified. To undo: `rm -rf dashboard/ tests/test_dashboard_*.py run_dashboard.py`.

## Claude Code Handoff Prompt

```text
Read docs/plans/2026-04-05-feat-service-mesh-dashboard-plan.md.

PREREQUISITE: Write and pass tests/test_dashboard_ssrf.py (SSRF verify-first test) before any routes.

Repos and files in scope:
- dashboard/schema.sql
- dashboard/db.py
- dashboard/ssrf.py
- dashboard/services.py
- dashboard/keys.py
- dashboard/health.py
- dashboard/jobs.py
- dashboard/events.py
- dashboard/routes.py
- dashboard/app.py
- dashboard/auth.py
- dashboard/worker.py
- run_dashboard.py
- tests/test_dashboard_ssrf.py
- tests/test_dashboard_services.py
- tests/test_dashboard_keys.py
- tests/test_dashboard_health.py
- tests/test_dashboard_routes.py

Scope boundaries:
- No UI / HTML — JSON API only
- No webhook alerts
- Worker is a separate process — no Flask background threads
- Allow_redirects=False in all HTTP requests
- Never expose key material in GET responses

Key corrections from plan review: [fill after Codex review]

Acceptance criteria: see plan ## Acceptance Criteria section

Required checks: pytest tests/ -k dashboard -v

Stop conditions:
- If SSRF verify-first test fails, stop and report
- If requests library is unavailable, stop and report
```

## Sources

- Brainstorm: docs/brainstorms/2026-04-05-service-mesh-dashboard.md

## Feed-Forward

- **Hardest decision:** Single DB vs. domain modules. Domain modules chosen for testability — each module has a focused surface, but `create_app` must wire all blueprints.
- **Rejected alternatives:** Separate SQLite DBs per concern; monolithic `db.py`; Flask background threads for worker; unsalted SHA-256.
- **Least confident:** The aggregate dashboard query (correlated subquery per service for latest health) — correct but O(N) subqueries. Acceptable for MVP; document as known limitation.
