---
title: "Distributed Task Scheduler"
date: 2026-04-05
status: complete
origin: "autopilot run"
---

# Distributed Task Scheduler — Brainstorm

## Problem
Developers need a way to schedule recurring jobs using cron expressions (e.g., "run this every 5 minutes"), have those jobs automatically dispatched into a job queue when they come due, and be able to view the status of schedules (upcoming, overdue, completed) via a dashboard endpoint. Without this, recurring work must be manually triggered or handled by external cron daemons with no visibility.

## Context
- Flask + SQLite stack (matching existing job-queue and webhook-delivery projects in /workspace)
- Prior art in /workspace: job-queue system (atomic claims, status machine), webhook-delivery (next_run_at scheduling, claimed_at timeout anchor)
- "Distributed" in this context = SQLite row-locking as coordination; multiple workers can safely claim jobs without double-firing
- Three subsystems needed: (1) schedule submission API, (2) scheduler loop that spawns due jobs, (3) dashboard endpoint

## Options

### Option A: Embedded scheduler thread in Flask app
Run a background thread inside the Flask process that wakes every N seconds, queries for due schedules, and inserts job_runs into the queue table.
- **Pros:** Simple deployment, no extra processes, shares SQLite connection pool
- **Cons:** Thread safety with SQLite, Flask dev server doesn't support threads reliably, multiple gunicorn workers = multiple scheduler threads = duplicate fires

### Option B: Separate scheduler process (recommended)
A standalone `scheduler.py` script that runs as its own process (via systemd, Docker, or just `python scheduler.py`). It polls the schedules table, calculates next_run_at via cron expressions, and inserts into the job_runs queue.
- **Pros:** No thread safety issues, only one scheduler runs at a time, clear separation of concerns, easy to test in isolation
- **Cons:** Two processes to start/stop, slightly more ops overhead

### Option C: Use APScheduler or Celery Beat
Offload cron scheduling to an existing library.
- **Pros:** Battle-tested cron parsing, many features
- **Cons:** Adds heavyweight dependencies, hides the logic we need to control, doesn't fit the "learn by building" context of this project

## Tradeoffs
- **Option A vs B:** Thread safety is the deciding factor. SQLite + multiple gunicorn workers + background threads = recipe for duplicate job fires. Separate process wins on correctness.
- **Option B vs C:** We need to own the SQLite schema and claim logic (from prior lessons). A library like APScheduler stores its own state and fights with our schema.

## Decision
**Option B: Separate scheduler process.** Single `scheduler.py` that polls every 10 seconds. Uses `croniter` library for cron expression parsing (lightweight, no other deps). Atomic claim logic adapted from job-queue solution doc: SELECT id → UPDATE WHERE id AND status='pending' → rowcount check.

## Open Questions
1. What happens if the scheduler is down for an hour — do missed runs fire all at once, or skip to next scheduled time? (Decision: skip — only fire if `next_run_at <= now AND status = 'pending'`)
2. What cron library to use? `croniter` is smallest footprint.
3. What does "completed" mean on the dashboard — the schedule itself, or individual runs?
4. How far ahead does the dashboard show "upcoming"? (Decision: next 10 scheduled fires)

## Feed-Forward
- **Hardest decision:** Whether the scheduler loop should back-fill missed runs or skip them. Skipping is safer and simpler — back-filling could flood the queue after downtime.
- **Rejected alternatives:** Embedded Flask thread (thread safety), APScheduler (too opaque, wrong dependency for this project's learning goals)
- **Least confident:** SQLite WAL mode behavior under concurrent writes from scheduler process + Flask workers simultaneously. Need to verify WAL is enabled and that the job_runs insert is truly atomic under load.
