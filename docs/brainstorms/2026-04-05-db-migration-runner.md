---
title: "Database Migration Runner"
date: 2026-04-05
status: complete
origin: "autopilot session"
---

# Database Migration Runner — Brainstorm

## Problem

Services need a reliable way to evolve their database schema over time. Ad-hoc SQL scripts drift, lack ordering guarantees, can be applied twice, and have no rollback path. A migration runner solves this by: tracking which scripts have been applied, enforcing version order, supporting rollback via down-scripts, and preventing two processes from running migrations simultaneously.

## Context

- Target: SQLite (single-file DB, no native advisory locks)
- Runtime: Flask API for programmatic/remote control + CLI for local operation
- Migration files: SQL files with up/down sections or separate up/down files
- Prior lessons: BEGIN IMMEDIATE for atomicity, executescript() has implicit COMMIT, WAL for concurrent access, merge check+write into one transaction

## Options

### Option A: Directory-scan registration (filesystem as source of truth)
Migration files live in a `migrations/` directory. At startup and before each operation, the runner scans the directory for `NNNN_name.sql` files. No explicit "register" step — presence in the directory is registration.

**Pros:**
- Simple — drop a file, it's registered
- No separate registration API needed
- Consistent ordering via numeric prefix
- Industry standard (Flyway, Alembic, golang-migrate)

**Cons:**
- Directory path must be configured (env var or config)
- Can't register migrations remotely without file access

### Option B: Explicit registration via API
Migrations are POSTed to `/migrations` with `name`, `version`, `up_sql`, `down_sql` stored in the DB.

**Pros:**
- Works without filesystem access
- Migrations stored in DB alongside state

**Cons:**
- Non-standard — most teams expect SQL files on disk
- DB becomes the source of truth for schema — circular (migrations in the same DB they migrate)
- Re-registration on restart needed
- Harder to code review

### Option C: Hybrid — filesystem scan + optional API override
Scan directory by default; allow API clients to POST up/down SQL to register a migration by version number.

**Pros:**
- Flexible

**Cons:**
- Two registration paths to maintain, more edge cases

## File Format

### Option F1: Single-file with `-- migrate:up` / `-- migrate:down` markers
```sql
-- migrate:up
CREATE TABLE users (id INTEGER PRIMARY KEY, ...);

-- migrate:down
DROP TABLE users;
```

**Pros:** One file per migration, common convention (dbmate-style), easier to review

**Cons:** Parser needed for markers

### Option F2: Separate `_up.sql` and `_down.sql` files
`0001_create_users_up.sql`, `0001_create_users_down.sql`

**Cons:** Two files per migration, harder to keep in sync

## Tradeoffs

**Registration:** Option A (directory scan) wins. Industry standard, simpler, no circular dependency problem. CLI naturally has filesystem access; Flask API can be given the migrations path at startup.

**File format:** Option F1 (single file with markers) wins. One file per migration is easier to manage. Parser is simple — split on `-- migrate:down`.

**Lock strategy:**
- **SQLite advisory lock table row** (`migrations_lock` with a single `locked` INTEGER column): INSERT OR REPLACE with `locked=1` inside BEGIN IMMEDIATE, DELETE after. Gives distributed-style locking without OS-level file locks.
- **SQLite `BEGIN EXCLUSIVE`**: Holds exclusive lock for the duration of all migrations. Blocks all reads during migration — too aggressive for multi-reader setup.
- **Advisory row** wins: explicit, releasable, observable, works across processes and the Flask API.

**Dry-run mode:**
- Collect SQL that would run, return it without executing, rollback any test transaction
- Implementation: wrap all migration SQL in a BEGIN, then ROLLBACK instead of COMMIT
- SQLite DDL is transactional (unlike PostgreSQL which auto-commits DDL) ✓

## Decision

- **Registration:** Directory scan (`migrations/` directory, configurable via `MIGRATIONS_DIR` env var)
- **File format:** Single file with `-- migrate:up` / `-- migrate:down` markers, filename `NNNN_description.sql` (4-digit version prefix)
- **Lock:** Advisory `migrations_lock` table row, acquired with `BEGIN IMMEDIATE` INSERT
- **Dry-run:** Real transaction, ROLLBACK at end; return SQL statements that would have run
- **CLI commands:** `migrate up [--dry-run]`, `migrate down [--steps N] [--dry-run]`, `migrate status`
- **Flask API routes:** `POST /migrate/up`, `POST /migrate/down`, `GET /migrate/status`

## Schema

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,   -- e.g. "0001"
    name        TEXT NOT NULL,       -- e.g. "create_users"
    applied_at  TEXT NOT NULL,       -- ISO8601 UTC
    checksum    TEXT NOT NULL        -- SHA-256 of up_sql for tampering detection
);

CREATE TABLE IF NOT EXISTS migrations_lock (
    id          INTEGER PRIMARY KEY CHECK (id = 1),  -- only one row allowed
    locked_at   TEXT NOT NULL,
    locked_by   TEXT NOT NULL        -- process ID or request ID
);
```

## Open Questions

1. **Multi-step up:** Should `migrate up` apply all pending or just one? → All pending (standard behavior), with `--target VERSION` to stop at a specific version.
2. **Down steps:** How many to roll back? → Default 1, configurable with `--steps N`.
3. **Checksum mismatch:** If an applied migration file is modified on disk, what happens? → Return error with which version was tampered; block further migrations.
4. **Target DB vs migrations DB:** Same SQLite file for `schema_migrations` table and the user's data? → Yes, same DB. The migrations table tracks what's applied to that DB.

## Feed-Forward

- **Hardest decision:** Lock strategy — advisory row vs. SQLite-native locking. Advisory row chosen because it's explicit, observable, releasable on crash via TTL or admin endpoint, and doesn't block readers during migration.
- **Rejected alternatives:** Option B (API-based registration) — circular dependency and non-standard; `BEGIN EXCLUSIVE` for locking — blocks all reads, too aggressive; separate up/down files — two files per migration adds unnecessary friction.
- **Least confident:** Dry-run correctness for DDL in SQLite. SQLite DDL IS transactional, so wrapping in a transaction and rolling back should work. But if a migration mixes DDL + DML with triggers or virtual tables, the rollback behavior may surprise. Need a verify-first test before implementing the dry-run path.
