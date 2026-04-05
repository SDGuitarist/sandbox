---
title: "Service Mesh Dashboard"
date: 2026-04-05
tags: [flask, sqlite, dashboard, health-check, api-keys, job-queue, events, ssrf]
module: dashboard
lesson: events.service_id should use ON DELETE SET NULL not CASCADE — ON DELETE CASCADE deletes the service.deleted audit event along with the service, making deletion unauditable; SET NULL preserves the record while breaking the dangling FK reference
origin_plan: docs/plans/2026-04-05-feat-service-mesh-dashboard-plan.md
origin_brainstorm: docs/brainstorms/2026-04-05-service-mesh-dashboard.md
---

# Service Mesh Dashboard

## Problem

When running multiple services, operators need a single pane of glass: register services with health check URLs, authenticate dashboard callers with API keys, queue periodic health probes, display aggregate status, and browse a timestamped event timeline.

## Solution

Standalone Flask + SQLite JSON API implementing four patterns in one service:
- **Service registry:** CRUD for services with SSRF-validated health_check_url
- **API key auth:** Salted SHA-256, prefix lookup, `hmac.compare_digest`, `immediate=True` in auth middleware
- **Health job queue:** Atomic claim (`SELECT id → UPDATE WHERE id AND status='pending' → rowcount`), `enqueue_pending_services` with `NOT IN` subquery inside `BEGIN IMMEDIATE`
- **Event timeline:** Append-only `events` table, cursor pagination (`id > after_id`, `next_cursor = events[-1]["id"]`)
- **Worker + Scheduler:** Separate processes (not Flask threads); worker uses `allow_redirects=False`

12 routes: `POST/GET /services`, `GET/DELETE /services/<id>`, `POST /services/<id>/check`, `GET /dashboard`, `POST/GET /keys`, `DELETE /keys/<id>`, `GET /events`.

## Why This Approach

- **Domain modules over monolithic `db.py`:** Each concern (services, keys, health, jobs, events) has its own module — independently testable, mirrors individual service patterns from prior cycles.
- **Separate processes for worker/scheduler:** Flask background threads fire N times under gunicorn multi-worker. Separate processes are correct.
- **`immediate=True` in auth middleware:** Without it, `validate_key` (SELECT → UPDATE last_used_at) has a TOCTOU window where a revoked key can pass the check after being revoked.
- **`allow_redirects=False` in worker:** SSRF layer 2 — prevents redirect-based bypass of the registration-time IP check.

## Risk Resolution

> **Flagged risk:** "SSRF DNS rebinding gap — register with public DNS that later resolves to 127.0.0.1 after validation."

**What actually happened:** Both SSRF layers implemented and tested. Layer 1 (hostname resolution + private IP check at registration) blocks direct private IP registrations. Layer 2 (`allow_redirects=False` in worker) blocks redirect-based SSRF. DNS rebinding is documented as a known gap — the worker's initial connection is to the service's resolved public IP, so rebinding after registration would only affect subsequent DNS lookups. Documented in `ssrf.py` module docstring.

**Lesson learned:** The link-local check must come BEFORE the private-IP check in `_check_ip`. In Python 3.12, `169.254.x.x` addresses are classified as both `is_link_local` and `is_private` — if you check `is_private` first, the error message says "private address" not "link-local address", which fails a test expecting "link-local".

## Key Decisions

| Decision | Chosen | Rejected | Reason |
|----------|--------|----------|--------|
| events FK | ON DELETE SET NULL | ON DELETE CASCADE | CASCADE deletes the service.deleted event along with the service — audit records must survive |
| Auth timing | `immediate=True` in middleware | Non-immediate read | Closes TOCTOU window: revoked key could pass check during the gap between SELECT and UPDATE |
| 3xx health status | `degraded` | `healthy` | With `allow_redirects=False`, 3xx means the service isn't answering at its registered URL |
| `complete_job` guard | `AND status='running'` | No guard | Prevents silent double-complete — idempotent and safe to retry |
| Event `service_id` on deletion | Preserved (NULL) | Deleted | `service.deleted` event must survive to be visible in audit timeline |

## Gotchas

- **`events.service_id ON DELETE SET NULL`:** Review initially suggested CASCADE (which was implemented and broke `test_delete_service_appends_event` — the `service.deleted` event itself got deleted). Correct semantic for an audit log is SET NULL: records survive, FK reference is cleared.
- **link-local before private in SSRF check:** Python 3.12 classifies 169.254.x.x as both `is_link_local` and `is_private`. Check `is_link_local` first to get the right error message.
- **`validate_key` needs `immediate=True`:** The SELECT+UPDATE pattern in `validate_key` (check not revoked, then update last_used_at) is a TOCTOU gap without a write lock. Auth middleware must use `immediate=True`.
- **`enqueue_pending_services` NOT IN with NOT NULL service_id:** The `NOT IN` subquery is safe because `health_jobs.service_id` is `NOT NULL` — a NULL in the subquery would cause `NOT IN` to silently return no rows. Always use `NOT NULL` constraints when using `NOT IN` subqueries.

## Feed-Forward

- **Hardest decision:** `events.service_id` FK semantics — CASCADE vs SET NULL. Discovered during test failures after applying the review's P1 fix (adding CASCADE). SET NULL is correct for audit logs.
- **Rejected alternatives:** Monolithic `db.py`; Flask background threads; ON DELETE CASCADE on events; missing `immediate=True` on auth.
- **Least confident:** The correlated subquery in `get_dashboard` (one subquery per service to find latest health result) is O(N) queries. Acceptable for small service counts but would need a `current_status` denormalization column for scale. Documented in plan.
