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
- **Incident 4 (May 8-9, 2026):** 1,690 leads lost during migration development. DB wiped multiple times during "verification testing" of new schema migrations. Restored to 1,211 (backup existed) but 2,901-lead state had no backup. Cost: real Apify credits + lost workshop prep time.
- Apify results vary between runs -- re-scraping does NOT recover identical leads.
- Total Apify credits wasted on redundant re-scrapes: ~8 runs.

## Incident 4 Root Cause (May 8-9, 2026)

**Different from incidents 1-3.** This was NOT concurrent access. This was running untested migration code (`init_db()` / `migrate_db()`) directly against the production DB during development.

The migration used `DROP TABLE outreach_queue` + `ALTER TABLE outreach_queue_new RENAME TO outreach_queue` inside `conn.executescript()` (implicit commits). A bug in the FK idempotency check (`str(sqlite3.Row)` returns object repr, not values) caused the migration to fire repeatedly when it should have been a no-op. Repeated migration runs against production with broken idempotency check wiped the DB.

**New failure mode discovered:** `executescript()` with implicit commits means if anything goes wrong mid-script, you get partial state with no rollback. The pre/post row count assertion catches it AFTER the fact but cannot undo it.

**Additional discovery:** Running `init_db()` on every CLI invocation means every `python run.py ...` call runs the full migration chain. If any migration has a bug, it fires on every single CLI call.

## Updated Rules (Combining All 4 Incidents)

1. **One process at a time** (incidents 1-3): Never run foreground commands while background tasks touch leads.db.
2. **Never run untested code against production** (incident 4): Always copy leads.db to /tmp and test there first. NEVER use default DB_PATH during development verification.
3. **Destructive migrations must be explicit** (incident 4): DROP TABLE should never fire from ordinary startup. Require an explicit `migrate` command with a flag.
4. **Back up after every successful operation** and verify the backup has data (all incidents).
5. **init_db() on every CLI call is dangerous** (incident 4): If it calls migration logic, bugs fire on every invocation.

## Codex Stabilization (May 9, 2026)

After incident 4, Codex hardened the codebase:
- Tests blocked from touching production leads.db
- Explicit production migration guard (raises MigrationRequired)
- Destructive migration removed from ordinary startup flow
- Explicit `python run.py migrate --allow-destructive-production` required
- Global DB job lock for write-heavy operations
- Production DB file checks (refuses to proceed if DB is missing or empty)
