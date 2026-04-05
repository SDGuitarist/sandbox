# URL Health Monitor

A Flask + SQLite URL health monitor. Register URLs to check, workers poll a job queue to perform HTTP health checks, results are stored with response times, and an alert endpoint returns degraded URLs.

## How It Works

Three components:
1. **Flask API** — register URLs, view results, get alerts
2. **scheduler.py** — enqueues health check jobs at each URL's configured interval
3. **worker.py** — claims jobs, performs HTTP checks, updates status

## Setup

```bash
pip install flask requests
cd url_health_monitor
python db.py    # creates health_monitor.db
```

## Start

```bash
# Terminal 1 — Flask API
python app.py        # runs on http://localhost:5006

# Terminal 2 — Scheduler (enqueues jobs at configured intervals)
python scheduler.py

# Terminal 3 — Worker (performs HTTP checks)
python worker.py
```

## API

### Register a URL

```bash
curl -X POST http://localhost:5006/urls \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "name": "example",
    "check_interval_seconds": 60,
    "failure_threshold": 2,
    "timeout_seconds": 10
  }'
# Returns: {"id": 1, "current_status": "unknown", ...}
```

### List monitored URLs

```bash
curl http://localhost:5006/urls
```

### Get URL details + last 10 check results

```bash
curl http://localhost:5006/urls/1
```

### Delete a URL

```bash
curl -X DELETE http://localhost:5006/urls/1
```

### Get alerts (degraded URLs)

```bash
curl http://localhost:5006/alerts
# Returns: {"alerts": [...]} — only URLs with current_status="degraded"
```

## Status transitions

| Status | Meaning |
|--------|---------|
| `unknown` | Fewer than `failure_threshold` checks completed |
| `healthy` | At least one of the last `failure_threshold` checks succeeded |
| `degraded` | All of the last `failure_threshold` checks failed |

A single success after `failure_threshold` failures immediately transitions to `healthy`.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HEALTH_MONITOR_DB` | `./health_monitor.db` | Path to SQLite database |
| `POLL_INTERVAL` | `10` (scheduler) / `2` (worker) | Seconds between polls |
| `WORKER_ID` | random UUID | Worker identifier for debugging |
