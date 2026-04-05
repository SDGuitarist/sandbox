---
title: "Service Mesh Dashboard"
date: 2026-04-05
status: complete
origin: "autopilot session"
---

# Service Mesh Dashboard — Brainstorm

## Problem

When running multiple services (URL shortener, job queue, API key manager, health monitor), operators need a single pane of glass: register services, check their health, track health history, authenticate API callers, queue recurring health probes, and browse a timestamped event timeline. Without this, operators poll each service manually, miss degradations, and have no audit trail.

## Context

- Build a **standalone** Flask + SQLite service — it does not read from other services' DBs
- It **implements** the patterns from prior services (API key auth, job queue, health checking, event log) in a single cohesive codebase
- Prior lessons apply directly: SSRF protection, salted SHA-256 keys, atomic job claim, cursor pagination on events, `next_run_at` inside `BEGIN IMMEDIATE`
- The "integrations" are: this service acts as the API key manager for dashboard access, the job queue for health probes, the health monitor for registered services, and the audit log for all events

## What We're Building

1. **Service registry** — register/list/delete services with `name`, `url`, `health_check_url`, `description`
2. **API key auth** — create keys scoped to a service registration (or global admin), validate on all mutating routes
3. **Health checker** — enqueue `health_check` jobs for each registered service; worker claims and executes HTTP GET to `health_check_url`, records result (status_code, response_time_ms, healthy/degraded/unknown)
4. **Aggregate dashboard** — `GET /dashboard` returns all services with their latest health status + counts
5. **Event timeline** — every service registration, deletion, health status change, and key creation appends to an `events` table; `GET /events` returns paginated cursor-based timeline
6. **Job queue** — `health_check_jobs` table; scheduler enqueues one job per service on a configurable interval; worker processes them

## Options

### Option A: Monolithic single-module approach
Everything in one `dashboard/` package — one `db.py` with all tables, one `routes.py` with all endpoints.

**Pros:** Simple, fewer files  
**Cons:** `db.py` becomes very large; hard to test subsystems independently

### Option B: Domain modules (chosen)
Separate modules for each concern: `services.py`, `keys.py`, `health.py`, `events.py`, `jobs.py` under `dashboard/`. Each module owns its DB functions and routes blueprint.

**Pros:** Matches prior service patterns, testable in isolation, clear ownership  
**Cons:** More files, need `create_app` to wire them

### Option C: Separate SQLite databases per concern
Each module gets its own `.db` file (like the separate services this replaces).

**Cons:** Cross-table JOIN for dashboard aggregate becomes a Python-side merge across multiple connections — unnecessary complexity for a single-process service. Rejected.

## Schema Sketch

```sql
-- Services
CREATE TABLE services (
    id          TEXT PRIMARY KEY,   -- UUID
    name        TEXT NOT NULL UNIQUE,
    url         TEXT,
    health_check_url TEXT NOT NULL,
    description TEXT,
    created_at  TEXT NOT NULL
);

-- API keys (global admin or per-service)
CREATE TABLE api_keys (
    id          TEXT PRIMARY KEY,
    prefix      TEXT NOT NULL,      -- first 8 chars for display
    key_hash    TEXT NOT NULL,      -- SHA-256(salt+key)
    salt        TEXT NOT NULL,
    label       TEXT NOT NULL,
    service_id  TEXT REFERENCES services(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    last_used_at TEXT,
    revoked     INTEGER NOT NULL DEFAULT 0
);

-- Health check results
CREATE TABLE health_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id      TEXT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    checked_at      TEXT NOT NULL,
    status          TEXT NOT NULL,  -- healthy | degraded | unknown
    status_code     INTEGER,
    response_time_ms INTEGER,
    error_message   TEXT
);

-- Job queue for health checks
CREATE TABLE health_jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id  TEXT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending | running | done | failed
    scheduled_at TEXT NOT NULL,
    claimed_at  TEXT,
    worker_id   TEXT,
    completed_at TEXT
);

-- Event timeline (append-only)
CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,   -- service.registered | service.deleted | health.changed | key.created | key.revoked
    service_id  TEXT,
    payload     TEXT NOT NULL,   -- JSON
    created_at  TEXT NOT NULL
);
```

## Key Design Decisions

### Authentication
Use the API key pattern from prior cycles: `secrets.token_hex(32)` for the key, `secrets.token_hex(16)` for the salt, store `SHA-256(salt + key)`. Display 8-char prefix. Validate with `hmac.compare_digest`. Middleware checks `Authorization: Bearer <key>` header on all mutating routes.

Admin keys (no `service_id`) can do everything. Per-service keys can only trigger health checks for their own service.

### Health check worker
A separate `worker.py` process (not Flask thread) claims jobs from `health_jobs` atomically:
- `SELECT id FROM health_jobs WHERE status='pending' AND scheduled_at <= datetime('now') ORDER BY scheduled_at ASC LIMIT 1`
- `UPDATE health_jobs SET status='running', claimed_at=datetime('now'), worker_id=? WHERE id=? AND status='pending'` → check rowcount
- Fetch `health_check_url` by `service_id`, do `requests.get(..., timeout=5, allow_redirects=False)`
- Record result in `health_results`, update `health_jobs` to done/failed
- Append event if health status changed from last result

### Scheduler
`scheduler.py` polls every N seconds, enqueues one job per service if no pending/running job exists:
```sql
INSERT INTO health_jobs (service_id, status, scheduled_at)
SELECT id, 'pending', datetime('now')
FROM services
WHERE id NOT IN (
    SELECT service_id FROM health_jobs WHERE status IN ('pending', 'running')
)
```
Run inside `BEGIN IMMEDIATE`. Compute `scheduled_at` inside the transaction.

### SSRF protection
At service registration, resolve `health_check_url` hostname and reject if it maps to private/loopback/link-local IPs (`ipaddress` module, same as url-health-monitor). Also `allow_redirects=False` in worker.

### Aggregate dashboard
```sql
SELECT s.*, h.status, h.checked_at, h.response_time_ms
FROM services s
LEFT JOIN health_results h ON h.id = (
    SELECT id FROM health_results WHERE service_id = s.id ORDER BY id DESC LIMIT 1
)
```
Returns one row per service with latest health status.

### Event timeline
Append-only `events` table. Cursor pagination: `WHERE id > ? ORDER BY id ASC LIMIT ?`. `next_cursor = rows[limit-1]["id"]`.

## What We're NOT Building

- Actual cross-service DB integration (reading from other services' SQLite files)
- A UI (API only, JSON responses)
- Webhook alerts on degradation (deferred)
- Rate limiting (deferred, prior pattern available)

## Feed-Forward

- **Hardest decision:** Whether to use a single `db.py` or domain modules. Domain modules chosen — they mirror how the prior individual services were built and enable independent testing. The cost is more files and a larger `create_app` wiring step.
- **Rejected alternatives:** Separate SQLite DBs per concern (Python-side JOINs, unnecessary complexity); monolithic `db.py` (hard to test in isolation); using `hmac.compare_digest` with unsalted hash (rainbow table risk).
- **Least confident:** SSRF check at registration time is necessary but may not be sufficient — DNS rebinding can bypass it (register with a public DNS that resolves to 127.0.0.1 after validation). For this MVP, document the gap and use `allow_redirects=False` in the worker as the second line of defense.
