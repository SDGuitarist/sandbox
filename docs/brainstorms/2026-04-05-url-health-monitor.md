---
title: "URL Health Monitor"
date: 2026-04-05
status: complete
origin: "autopilot run"
---

# URL Health Monitor — Brainstorm

## Problem
Teams need to know when their URLs are down or slow without setting up complex external monitoring. A lightweight service that registers URLs, periodically dispatches health check jobs, stores response time history, and exposes an alert endpoint showing which URLs are currently degraded.

## Context
- Flask + SQLite stack (consistent with all prior projects in /workspace)
- Prior art: job-queue (atomic worker claim), task-scheduler (scheduled interval firing), webhook-delivery (retry + claimed_at timeout)
- Workers perform actual HTTP GET requests to the registered URLs
- "Degraded" = recent checks failed or response time exceeded threshold
- Three subsystems: (1) URL registry API, (2) scheduler that enqueues health check jobs, (3) workers that claim jobs and do HTTP checks

## Options

### Option A: Workers poll the job queue directly (recommended)
A standalone `worker.py` polls the `health_check_jobs` table for pending jobs, claims them atomically, performs the HTTP check, records results, and loops. A separate `scheduler.py` enqueues new jobs at configured intervals (same pattern as task-scheduler).
- **Pros:** Clean separation of concerns, atomic claim prevents duplicate checks, aligns with all prior solution patterns in this workspace
- **Cons:** Two extra processes to manage (scheduler + worker)

### Option B: Workers hit URLs on a fixed timer without a job queue
Worker processes sleep N seconds, wake up, check all registered URLs, sleep again. No queue table.
- **Pros:** Simpler, fewer tables
- **Cons:** No history of individual check attempts, no retry logic, no way to track "is this URL currently being checked?", hard to distribute across multiple workers without overlap

### Option C: Flask background thread does all checks
Same as task-scheduler's rejected Option A — background thread in Flask runs checks.
- **Cons:** Thread safety with SQLite, doesn't survive gunicorn multi-worker mode, duplicate checks per worker

## Tradeoffs
- Option A vs B: History and retry logic are explicit requirements. A job queue provides both naturally; a timer loop provides neither.
- Option A vs C: Same thread-safety issue as task-scheduler — rejected for same reasons.

## Decision
**Option A: Job queue + separate scheduler + separate workers.** Reuses all proven patterns from this workspace. Schema: `monitored_urls` + `check_jobs` tables. Scheduler enqueues `check_jobs` at each URL's `check_interval_seconds`. Workers claim jobs, perform HTTP GET with timeout, store result in `check_results` table and update `monitored_urls.last_status`.

Alert endpoint: `GET /alerts` returns URLs where the last N checks all failed OR average response time > threshold.

## Open Questions
1. What HTTP timeout for checks? Default 10 seconds.
2. What constitutes "degraded"? Last check failed OR last 3 checks failed (configurable)? Decision: configurable `failure_threshold` per URL (default 1).
3. How long to keep history? No automatic pruning for now — scope creep.
4. Should workers retry failed checks? Decision: yes, max_retries=3 with simple fixed delay (not exponential — health checks want fast retries).
5. What HTTP method? GET only — the most common and safe.

## Feed-Forward
- **Hardest decision:** Whether to make "degraded" stateful (track a `current_status` field that transitions healthy→degraded after N failures) or computed dynamically from recent check_results. Stateful is simpler for the alert query but requires a state machine. Dynamic is more flexible but requires a subquery on every alert request. Decision: stateful `current_status` field updated by worker after each check.
- **Rejected alternatives:** Background Flask thread (multi-worker duplicate checks), timer-loop worker without queue (no history, no retry, no concurrency safety), dynamic degraded query without stateful field (slow alert endpoint at scale).
- **Least confident:** Whether `requests` library is available in the environment, and whether outbound HTTP from the container will succeed. Need to verify `pip install requests` works and that external HTTP GET calls are not firewalled before writing worker logic.
