# Distributed Task Scheduler

A Flask + SQLite task scheduler that accepts jobs with cron expressions,
spawns them into a job queue when due, and provides a dashboard endpoint.

## How It Works

Three components:
1. **Flask API** — submit schedules, check status
2. **scheduler.py** — separate process that polls for due schedules and spawns job_runs
3. **SQLite** — `schedules` table + `job_runs` table, WAL mode for concurrent safety

## Setup

```bash
pip install flask "croniter>=2.0,<3.0"
cd task_scheduler
python db.py           # creates scheduler.db with schema
```

## Start

```bash
# Terminal 1 — Flask API
python app.py          # runs on http://localhost:5005

# Terminal 2 — Scheduler process
python scheduler.py    # polls every 10 seconds
```

## API

### Submit a schedule

```bash
curl -X POST http://localhost:5005/schedules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "cleanup-job",
    "cron_expr": "*/5 * * * *",
    "payload": {"action": "cleanup", "target": "tmp"}
  }'
# Returns: {"id": 1, "next_run_at": "2026-04-05 12:05:00", ...}
```

### List schedules

```bash
curl http://localhost:5005/schedules
```

### Get schedule + recent runs

```bash
curl http://localhost:5005/schedules/1
```

### Pause / resume / delete a schedule

```bash
curl -X PATCH http://localhost:5005/schedules/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "paused"}'

# status options: active, paused, deleted
```

### Dashboard

```bash
curl http://localhost:5005/dashboard
# Returns:
# {
#   "upcoming": [...],   # next 10 scheduled fires
#   "overdue":  [...],   # schedules past due with no pending run
#   "completed": [...]   # last 20 completed job_runs
# }
```

## Cron expression syntax

Uses [croniter](https://github.com/kiorky/croniter) — standard 5-field cron:

```
*    *    *    *    *
|    |    |    |    |
min  hour day  mon  weekday
```

Examples:
- `* * * * *` — every minute
- `*/5 * * * *` — every 5 minutes
- `0 9 * * 1-5` — 9am on weekdays

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULER_DB` | `./scheduler.db` | Path to SQLite database |
| `POLL_INTERVAL` | `10` | Seconds between scheduler polls |

## Design notes

- **Separate processes**: Flask and scheduler run independently — no background threads, no gunicorn worker conflicts
- **Atomic claim**: scheduler advances `next_run_at` and inserts `job_run` inside `BEGIN IMMEDIATE` — no duplicate fires even with multiple scheduler processes
- **Missed runs skipped**: if the scheduler is down, it picks up where it left off (next scheduled time) rather than back-filling all missed runs
- **WAL mode**: SQLite WAL + `busy_timeout=5000ms` ensures concurrent reads/writes don't immediately fail
