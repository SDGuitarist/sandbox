---
title: "Distributed Task Scheduler"
date: 2026-04-05
tags: [scheduling, cron, sqlite, flask, job-queue, atomicity]
module: task_scheduler
lesson: "For cron schedulers using SQLite, compute next_run_at INSIDE the BEGIN IMMEDIATE transaction — not before it — or stale clock snapshots will set next_run_at in the past and cause immediate duplicate fires."
origin_plan: docs/plans/2026-04-05-feat-distributed-task-scheduler-plan.md
origin_brainstorm: docs/brainstorms/2026-04-05-distributed-task-scheduler.md
---

# Distributed Task Scheduler

## Problem

Recurring jobs need to fire on cron schedules (e.g., "every 5 minutes"), be dispatched into a job queue as individual runs, and be visible on a dashboard showing upcoming, overdue, and completed executions. Without this, recurring work requires external cron daemons with no visibility or coordination.

## Solution

Three components in `task_scheduler/`:

1. **Flask API** (`app.py`, `routes.py`) — `POST /schedules` to submit cron jobs, `GET/PATCH /schedules` to manage them, `GET /dashboard` for status overview
2. **Scheduler process** (`scheduler.py`) — standalone Python process, polls every 10 seconds, atomically claims due schedules and inserts `job_runs`
3. **SQLite** (`schema.sql`, `db.py`) — `schedules` + `job_runs` tables, WAL mode + `busy_timeout=5000ms` on every connection

The key design: scheduler is a **separate process**, not a background thread in Flask. One process = no gunicorn multi-worker duplicate fires.

## Why This Approach

- **Rejected: Embedded Flask thread** — SQLite + multiple gunicorn workers = multiple scheduler threads = duplicate job fires. Thread safety is the deciding factor.
- **Rejected: APScheduler/Celery Beat** — Heavyweight dependencies that store their own state and fight with our schema. Doesn't match the learning goals of building atomic claim logic explicitly.
- **Rejected: Back-filling missed runs** — If the scheduler is down for an hour, back-filling could flood the queue. Skip to next scheduled time instead.

## Risk Resolution

> **Flagged risk:** "SQLite WAL mode behavior under concurrent writes from scheduler process + Flask workers simultaneously. Need to verify WAL is enabled and that the job_runs insert is truly atomic under load."

**What actually happened:** WAL mode itself worked fine — the Phase 1 smoke test (two concurrent connections, simultaneous writes) passed without SQLITE_BUSY. The real atomicity bug was subtler: `_next_run_at` was being computed BEFORE `BEGIN IMMEDIATE`, using a `now` snapshot captured at the start of the poll cycle. Under load or with a stalled poll loop, this stale `now` could set `next_run_at` to a value that was still in the past, causing the schedule to fire again on the very next poll (duplicate runs). Fix: move `_next_run_at` inside the `BEGIN IMMEDIATE` block so it always uses a fresh timestamp.

**Lesson learned:** When the plan says "verify WAL works," that passes quickly — but the real concurrent-write hazard is the transaction boundary, not WAL mode. The question to ask is: "Is anything that affects the row state being computed outside the lock?" If yes, move it inside.

## Key Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Missed run behavior | Skip (advance to next occurrence after now) | Back-fill after downtime could flood queue |
| Scheduler architecture | Separate process | Thread safety with gunicorn workers |
| Cron library | `croniter` | Smallest footprint, no external state |
| next_run_at base | `now` (not `old_next_run_at`) | Skip, not back-fill; prevents catching up |
| Claim mechanism | CAS via UPDATE rowcount | No external locking needed; SQLite serializes writes |

## Gotchas

1. **Compute next_run_at INSIDE BEGIN IMMEDIATE** — not before. The `now` snapshot used as base must be taken inside the transaction lock, or stale clock values set `next_run_at` in the past.

2. **Per-schedule try/except with continue, not re-raise** — If one schedule has a bad `cron_expr` (hand-edited DB row), a `CroniterBadCronError` must skip that schedule, not abort the entire poll cycle. Use `continue` not `raise`.

3. **OperationalError on BEGIN IMMEDIATE per-schedule** — If another writer holds the lock beyond `busy_timeout`, SQLite raises immediately. Catch it per-schedule and skip (retry next poll), not at the outer poll level.

4. **Input validation before DB write** — `payload` must be validated as a dict (not string/int/array); `name` and `cron_expr` need length limits; `status` in PATCH must be type-checked as string before `.strip()` or you get AttributeError → 500.

5. **State machine enforcement on PATCH** — `deleted` → `active` must be rejected (409). Read existing status before updating; soft-delete is irreversible.

6. **Atomic claim = UPDATE rowcount check** — The CAS pattern: `UPDATE WHERE id=? AND next_run_at=<expected>` then check `rowcount`. If 0, another process claimed it first. Do not retry; move on.
