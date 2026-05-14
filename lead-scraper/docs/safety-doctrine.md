# Lead Scraper Safety Doctrine

**Date:** 2026-05-10
**Status:** Active
**Phase:** Rebuild-in-Place Phase 0 (Architecture Freeze)
**Origin:** docs/brainstorms/2026-05-09-rebuild-in-place-epic-brainstorm.md

## Core Principle

**Production data is a protected asset, not a default file.**

Every operation that touches `leads.db` must prove it cannot destroy data before it runs.

## Incident History

| # | Date | Cause | Leads Lost | Root Cause |
|---|---|---|---|---|
| 1 | May 5 | Concurrent SQLite access | 772 | Two processes on leads.db |
| 2 | May 5 | Concurrent SQLite access | 1,093 | Same -- no backup existed |
| 3 | May 5 | Concurrent SQLite access | 484 (restored) | Same -- manual backup saved it |
| 4 | May 8-9 | Untested migration on production | 1,690 | Bug in FK idempotency check + executescript implicit commits |

## Write Path Inventory (41 operations, 6 modules)

### CRITICAL Risk (3 operations) -- can destroy entire tables

| Module | Function | Operation | Guards |
|---|---|---|---|
| db.py | `_migrate_needs_review_status()` | DROP TABLE + CREATE TABLE + INSERT | `_assert_not_pytest_production`, `_destructive_migration_allowed`, pre/post row count assertion, WAL backup |

### HIGH Risk (2 operations) -- can delete individual leads or initialize schema

| Module | Function | Operation | Guards |
|---|---|---|---|
| models.py | `delete_lead()` | DELETE FROM leads | CSRF header check (web), single-lead only |
| db.py | `init_db()` | executescript(schema.sql) | `_assert_not_pytest_production`, `allow_create_production` flag |

### MEDIUM Risk (8 operations) -- can clear or overwrite data in bulk

| Module | Function | Operation | Guards |
|---|---|---|---|
| db.py | `migrate_db()` | ALTER TABLE ADD COLUMN | Column-existence check, WAL backup |
| models.py | `merge_leads()` | UPDATE + DELETE (duplicates) | Completeness scoring, keeps most-complete lead |
| campaign.py | `skip_all_messages()` | UPDATE status + clear hook fields | Status guard (draft only) |
| run.py | `_refresh_stale_leads()` | UPDATE SET NULL (hooks, segments) | Time-based filter (--days flag) |
| app.py | `delete()` | DELETE via models.delete_lead() | CSRF check |

### LOW Risk (28 operations) -- normal CRUD with atomic guards

| Module | Table | Count | Pattern |
|---|---|---|---|
| campaign.py | outreach_queue | 17 | All use atomic WHERE status=X + rowcount check |
| account.py | sender_accounts | 10 | All use atomic WHERE status=X + rowcount check |
| enrich.py | leads | 6 | COALESCE prevents overwriting existing values |
| ingest.py | leads | 1 | INSERT OR IGNORE (dedup) |
| campaign.py | campaigns, campaign_leads | 2 | INSERT with ON CONFLICT DO NOTHING |

## Single-Writer Rule

| Table | Owner Module | Enforced By |
|---|---|---|
| leads (INSERT) | ingest.py | Only module with INSERT INTO leads |
| leads (UPDATE) | enrich.py | COALESCE pattern, enrichment columns only |
| leads (DELETE) | models.py | Only module with DELETE FROM leads |
| campaigns | campaign.py | Module docstring, convention |
| campaign_leads | campaign.py | Module docstring, convention |
| outreach_queue | campaign.py | Module docstring, convention |
| sender_accounts | account.py | Module docstring, convention |

## Safety Guards in Place (Phase 1 -- Shipped)

| Guard | What It Blocks | Location |
|---|---|---|
| `_is_production_db()` | Identifies real leads.db | db.py |
| `_assert_not_pytest_production()` | Tests touching production | db.py, called in all migration/init paths |
| `_destructive_migration_allowed()` | DROP TABLE without explicit flag | db.py |
| `MigrationRequired` exception | Auto-migration on startup | db.py, raised when production needs migration |
| `_backup_wal_safe()` | Schema changes without backup | db.py, called before any ALTER/DROP |
| `_assert_production_file_ready()` | Operations on missing/empty DB | db.py |
| Pre/post row count assertion | Silent data loss during migration | `_migrate_needs_review_status()` |
| Explicit `migrate` command | Accidental migration from normal CLI | run.py (`migrate --allow-destructive-production`) |

## Rules (Non-Negotiable)

### For All Agents and Sessions

1. **Never run concurrent processes on leads.db.** One process at a time. Always.
2. **Never run untested code against production.** Copy to /tmp first: `cp leads.db /tmp/test_copy.db`
3. **Never use `init_db()` or `migrate_db()` against production from tests or experiments.**
4. **Back up before every destructive operation.** `_backup_wal_safe()` handles this automatically for migrations.
5. **Verify count before AND after.** `SELECT COUNT(*) FROM leads` before, same after. If different, stop.
6. **Trust the guards.** If `MigrationRequired` is raised, use the explicit migrate command. Don't bypass.

### For Migration Code

7. **Destructive migrations require `--allow-destructive-production`.**
8. **Always use explicit column names in INSERT ... SELECT.** Never use `SELECT *`.
9. **Pre-migration row count must equal post-migration row count (asserted, not just printed).**
10. **Skip condition must check ALL targets.** Don't skip on partial migration state.

### For Feature Work

11. **New modules must not import sqlite3 directly.** Use `get_db()` context manager.
12. **New write operations must follow single-writer rule.** One module per table.
13. **New status transitions must be atomic.** `UPDATE ... WHERE status = X`, check rowcount.
14. **No new DROP TABLE operations without a rebuild phase plan.**

## Classification: Safe Feature Work (Allowed Now)

- Running scrapers (existing safe paths via ingest.py)
- Quality gate (reads DB, writes through campaign.py)
- Browser sender (reads DB, writes through campaign.py + account.py)
- New enrichment steps (follows enrich.py COALESCE pattern)
- Report/export commands (read-only)
- New CLI commands that read data

## Classification: Unsafe (Requires Phase 2+ Rebuild)

- Any new table that needs DROP TABLE migration path
- Modifications to schema.sql or schema_campaigns.sql
- Changes to `init_db()` or `migrate_db()` behavior
- Any code that opens leads.db without `get_db()`

## Verification Checklist (Run Before Any DB Work)

```bash
# 1. Check current lead count
sqlite3 leads.db "SELECT COUNT(*) FROM leads"

# 2. Check backup exists
ls -la leads.backup-*.db | tail -1

# 3. Verify guards are active
python -c "from db import _is_production_db; print(_is_production_db('leads.db'))"

# 4. Verify tests don't touch production
python -m pytest tests/test_db_safety.py -v

# 5. After any operation, re-check count
sqlite3 leads.db "SELECT COUNT(*) FROM leads"
```

## Phase 0 Status: COMPLETE

All deliverables met:
- [x] Safety doctrine document (this file)
- [x] Inventory of all 41 DB-touching code paths
- [x] Classification by risk level (3 critical, 2 high, 8 medium, 28 low)
- [x] Decision log: single-writer rule preserved, guards shipped, rebuild Phases 2-5 deferred post-workshop

## Phase 1 Status: COMPLETE (shipped in commit 27a2ef4)

All deliverables met:
- [x] Hard boundary between production and test DB paths
- [x] Environment-aware DB path resolution
- [x] Tests that verify the boundary holds (test_db_safety.py)
- [x] All tests use explicit tmp_path

## Feed-Forward

- **Hardest decision:** Whether to audit all 41 write paths now vs. just the migration paths. Full audit wins because Incidents 1-3 came from concurrent access (any write path), not just migrations.
- **Rejected alternatives:** Partial audit of migration-only paths (misses the concurrent access vector).
- **Least confident:** Whether the current guards catch ALL wipe vectors. The inventory found no unguarded destructive paths, but a new module could bypass the guards by importing sqlite3 directly instead of using get_db(). Rule #11 prevents this by convention, not by enforcement. Phase 2 (migration rebuild) would add enforcement.
