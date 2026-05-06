---
title: Concurrent SQLite Access Wipes Data -- Never Touch leads.db During Background Tasks
date: 2026-05-05
updated: 2026-05-06
tags: [lead-scraper, database, data-loss, sqlite, concurrency]
failure_class: concurrent-db-access
---

## Problem

Lost leads data three times in one session. 772 leads, then 1,093 leads, then 484 leads (restored from backup). Every loss happened when a foreground process touched leads.db while a background process was also using it.

## Root Cause (Confirmed)

**Concurrent SQLite access through separate connections.** NOT `init_db()` itself -- the schema uses `CREATE TABLE IF NOT EXISTS` and is safe when run alone.

The pattern every time:
1. Background task (scrape or enrichment) running against leads.db via `run.py`
2. Foreground command opens a separate connection to the same DB (query, import, or debug test)
3. WAL-mode SQLite with two competing connections causes the table to appear missing or data to vanish
4. Background task fails with `no such table: leads` on next INSERT

**Timeline of third incident (confirmed):**
- 17:11 UTC: Background scrape starts, `init_db()` runs fine, table exists
- ~17:15 UTC: Foreground debug test opens raw `sqlite3.connect()` to same DB, then calls `init_db()` through a second connection
- 17:26 UTC: Background scrape tries to INSERT -- `no such table: leads`

The foreground debug test was the cause. Two connections to WAL-mode SQLite, one running `executescript()` while another has an open transaction, caused the table to disappear from the background process's view.

## The Rule

**NEVER touch leads.db while a background process is running against it. Not even to read it.**

- No `sqlite3 leads.db` queries
- No Python scripts importing from `db.py`
- No `run.py` commands (even `export`)
- No foreground enrichment while background scrape is running
- NOTHING until the background task completes

## Safe Workflow

```
1. Run operation (scrape, enrich, import) -- wait for completion
2. Verify count: sqlite3 leads.db "SELECT COUNT(*) FROM leads"
3. Back up: cp leads.db leads.backup-safe-$(date +%Y%m%d-%H%M%S).db
4. Run next operation -- wait for completion
5. Verify and back up again
6. Repeat
```

## Prevention

- Run all DB operations sequentially, never in parallel
- Back up after every successful operation before starting the next
- Use `sqlite3` CLI for quick counts, never Python `db.py` imports
- If a background task is running, do NOT check on the DB -- check the task output file instead

## Cost

- Incident 1: 772 leads lost. Re-scraped to recover ~734.
- Incident 2: 1,093 leads lost (734 + 359 new). No backup existed.
- Incident 3: 484 leads nearly lost. Restored from manual backup.
- Apify results vary between runs -- re-scraping does NOT recover identical leads.
- Total Apify credits wasted on redundant re-scrapes: ~6 runs.
