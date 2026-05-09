# CODEX HANDOFF: Production Database Keeps Getting Wiped

## Urgency

This is HIGH STAKES. The user has a workshop on May 30 and needs 3,000+ leads to promote it. The database currently has 1,211 leads. It previously had 2,901 but Claude Code wiped it during migration work on May 8-9. The lost 1,690 leads cost real money (Apify credits) to scrape and must be re-scraped. Every day without those leads is a day closer to the workshop with insufficient pipeline.

## The Problem

The production database (`leads.db`) has been wiped at least 3 times across different sessions. Claude Code was unable to diagnose the root cause or prevent recurrence despite adding guards. The most recent incident happened TODAY (May 9, 2026) during Phase 1 implementation of a browser outreach sender feature.

## What Happened (May 8-9, 2026)

1. Claude Code implemented schema migrations in `db.py` that add a `sender_accounts` table and recreate `outreach_queue` (DROP TABLE + INSERT + RENAME pattern).
2. During "verification testing," Claude Code ran `init_db()` directly against the production `leads.db` multiple times instead of testing on a copy.
3. A bug in the FK idempotency check (`str(sqlite3.Row)` returns object repr, not values) caused the migration to fire repeatedly when it should have been a no-op.
4. The database was wiped to an empty state. Restored from backup (1,211 leads), but the 2,901-lead state had no backup.
5. Claude Code then added a "production guard" but during debugging that guard, managed to wipe the DB AGAIN (at least once more).
6. The fundamental problem was never conclusively diagnosed — Claude Code couldn't determine exactly which operation zeroes out the data.

## Prior Incidents (Before May 8)

The user's CLAUDE.md contains: "NEVER run concurrent processes on leads.db (lost 1,093 leads TWICE previously)." This is at least the THIRD time data has been lost from this database.

## Current State of the Code

### Files Changed (all committed and pushed to master):
- `db.py` — restructured `migrate_db()`, added `_create_sender_accounts()`, `_migrate_needs_review_status()`, added production guard (`_destructive_migration_allowed()`)
- `account.py` (new) — sender account CRUD
- `browser_sender.py` (new) — Playwright DM automation
- `quality_gate.py` (new) — 3-tier verification
- `campaign.py` — 8 new functions for gate/send workflows
- `run.py` — new CLI commands (account, campaign gate/send/requeue/force-approve/force-skip)
- `requirements.txt` — added playwright>=1.40
- `.gitignore` — added .browser-profiles/
- `tests/test_account.py`, `tests/test_browser_sender.py`, `tests/test_quality_gate.py` (new)

### The Dangerous Pattern in `db.py`

`_migrate_needs_review_status()` does:
```
DROP TABLE outreach_queue;
ALTER TABLE outreach_queue_new RENAME TO outreach_queue;
```

This is inside `conn.executescript()` which has implicit COMMITs. If anything goes wrong mid-script, data is gone. The pre/post row count assertion catches it AFTER the fact but can't undo it.

`init_db()` runs on EVERY CLI command (line in `run.py:main()`):
```python
init_db()  # Always bootstrap the database
```

This means every `python run.py ...` invocation runs the full migration chain. If any migration has a bug or race condition, it fires on every single CLI call.

### The Guard That Was Added

```python
def _destructive_migration_allowed(db_path):
    if not _is_production_db(db_path):
        return True
    if os.environ.get("ALLOW_PRODUCTION_MIGRATE") == "1":
        return True
    if "pytest" in os.environ.get("_", ""):
        return True
    return False
```

This blocks DROP TABLE on production unless `ALLOW_PRODUCTION_MIGRATE=1` is set. But Claude Code couldn't verify this guard actually prevents all failure modes because it kept wiping the DB during testing.

## What Codex Needs To Do

1. **Diagnose the root cause.** Why does `init_db()` sometimes result in an empty database? Is it the `executescript()` implicit commits? A race between `get_db()` contexts? The `schema.sql`/`schema_campaigns.sql` interaction? Something else?

2. **Make it impossible to wipe production data.** The current guard is a start but insufficient. Consider:
   - Should `init_db()` run on every CLI invocation? Could it be a one-time setup command instead?
   - Should destructive migrations (DROP TABLE) be a separate explicit command, never called from `init_db()`?
   - Should there be a mandatory pre-migration row count check that ABORTS (not just asserts after) if the source table has data?

3. **Verify the fix works** by running tests against a COPY of the production DB, never the real one.

4. **Do NOT run any code against `/Users/alejandroguillen/Projects/sandbox/lead-scraper/leads.db` directly.** Always copy to `/tmp/` first. The current DB has 1,211 leads and must not be touched.

## Current Database State

- `leads.db`: 1,211 leads, 12 campaigns, 210 queue rows, 0 sender accounts
- `leads.backup-SAFE-DO-NOT-DELETE.db`: identical copy made with `cp` (no SQLite)
- `leads.backup-safe-20260508-132322.db`: the backup we restored from

## Key Files to Read

- `db.py` — all migration logic, the guard, `init_db()`, `get_db()`
- `schema.sql` — base leads table
- `schema_campaigns.sql` — campaigns + outreach_queue tables
- `run.py:main()` — where `init_db()` is called on every invocation
- `tests/test_migration.py` — existing migration tests (all pass)

## Tests

221 pass, 1 pre-existing failure (unrelated to migrations). Run with:
```
cd /Users/alejandroguillen/Projects/sandbox/lead-scraper
venv/bin/python -m pytest tests/ -v
```

## Do Not

- Do NOT run `init_db()` or `migrate_db()` against `leads.db`
- Do NOT trust Claude Code's assertion that the guard is sufficient
- Do NOT assume `CREATE TABLE IF NOT EXISTS` is safe in all execution paths
- Do NOT test on production — always `/tmp/test_copy.db`
