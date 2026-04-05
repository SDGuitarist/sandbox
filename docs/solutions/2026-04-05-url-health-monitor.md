---
title: "URL Health Monitor"
date: 2026-04-05
tags: [monitoring, health-check, job-queue, ssrf, flask, sqlite, workers]
module: url_health_monitor
lesson: "Any service that makes server-side HTTP requests based on user-supplied URLs is an SSRF target. Block private/loopback/link-local IPs at registration AND set allow_redirects=False in the worker — redirect bypass is the most common way registration-time checks are defeated."
origin_plan: docs/plans/2026-04-05-feat-url-health-monitor-plan.md
origin_brainstorm: docs/brainstorms/2026-04-05-url-health-monitor.md
---

# URL Health Monitor

## Problem

Teams need lightweight monitoring of their URLs without external services. Register URLs with check intervals, workers poll a job queue to perform HTTP health checks, store response time history, and an alert endpoint shows currently degraded URLs.

## Solution

Three components in `url_health_monitor/`:

1. **Flask API** — `POST /urls` (register with SSRF protection), `GET /urls`, `GET /urls/<id>`, `DELETE /urls/<id>`, `GET /alerts`
2. **scheduler.py** — enqueues `check_jobs` for URLs past their `check_interval_seconds`, with atomically-guarded NOT EXISTS inside BEGIN IMMEDIATE
3. **worker.py** — claims jobs atomically, performs `requests.get(..., allow_redirects=False)`, stores results, updates `current_status` (unknown/healthy/degraded) based on `failure_threshold`

Status logic: query last `failure_threshold` results by `checked_at DESC`. Fewer than threshold → `unknown`. All failed → `degraded`. Any success → `healthy`.

## Why This Approach

- **Rejected: Background Flask thread** — multi-worker duplicate checks, same reason as task-scheduler
- **Rejected: Timer-loop worker without queue** — no history, no retry, no concurrency safety
- **Rejected: Dynamic degraded query** — subquery on every alert request; stateful `current_status` = O(1) alert query

## Risk Resolution

> **Flagged risk:** "Whether `requests` library is available in the environment, and whether outbound HTTP from the container will succeed."

**What actually happened:** `requests` was available and outbound HTTP worked fine — confirmed before writing any worker code. The actual risk that emerged was SSRF: any service that makes server-side HTTP requests based on user-submitted URLs is an SSRF target by definition. This wasn't in the brainstorm Feed-Forward at all.

**Lesson learned:** "Does the HTTP library work?" is not the real risk for a health monitoring service. The real risk is always "can users weaponize the server's network position?" For any feature that accepts a URL and makes an HTTP request server-side, SSRF should be the first thing in the feed-forward, not an afterthought caught in review.

## Key Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| SSRF protection | Block private/loopback/link-local at registration + allow_redirects=False | Registration-time check alone is bypassable via redirect |
| Scheduler duplicate prevention | NOT EXISTS inside BEGIN IMMEDIATE (not before) | Pre-lock NOT EXISTS = TOCTOU race between two scheduler processes |
| Status semantics | One success among last N = healthy; fewer than N = unknown; all N failed = degraded | Asymmetric: fast recovery, slow degradation |
| Job timeout recovery | Reset running→pending after 120s via claimed_at anchor | Worker crash leaves job stuck; recovery fires in next poll cycle |
| Soft-delete | Cancel pending/running jobs on delete | Without this, deleted URLs keep being checked |

## Gotchas

1. **SSRF requires TWO fixes** — block private IPs at registration AND set `allow_redirects=False` in the worker. A redirect to `http://127.0.0.1` bypasses registration-time hostname checks entirely.

2. **Scheduler NOT EXISTS must be inside BEGIN IMMEDIATE** — if evaluated before the lock, two concurrent schedulers can both see "no pending job" and both insert, causing duplicate checks.

3. **Soft-delete must cancel pending jobs** — just marking the URL deleted leaves existing `check_jobs` rows running. Always `UPDATE check_jobs SET status='failed' WHERE url_id=? AND status IN ('pending','running')` in the same transaction as the soft-delete.

4. **Upper-bound all resource inputs** — `timeout_seconds` without a cap means workers block for hours. Cap at 30s; ensure `JOB_TIMEOUT_SECONDS > max(timeout_seconds)` so stale recovery is always reachable.

5. **Truncate error_message before storage** — `str(RequestException)` can include full URLs with credentials embedded in redirect chains. Truncate to 500 chars, use `type(e).__name__` not `str(e)` directly.

6. **response_time_ms can go negative** — use `max(0, int(time.time() * 1000) - start_ms)` to handle NTP corrections or clock drift.
