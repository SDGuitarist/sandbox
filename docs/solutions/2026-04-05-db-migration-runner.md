---
title: "Database Migration Runner"
date: 2026-04-05
tags: [flask, sqlite, migrations, cli, locking, dry-run]
module: migrator
lesson: Hold the advisory lock for the entire migration batch (not per-migration) to prevent TOCTOU windows; use sqlite3.complete_statement() not str.split(';') to parse multi-statement SQL
origin_plan: docs/plans/2026-04-05-feat-db-migration-runner-plan.md
origin_brainstorm: docs/brainstorms/2026-04-05-db-migration-runner.md
---

# Database Migration Runner

## Problem

Services need to evolve database schema over time safely. Ad-hoc SQL scripts lack ordering guarantees, can be applied twice, and have no rollback path. A migration runner tracks applied scripts, enforces version order, supports rollback via down-scripts, and prevents concurrent migrations.

## Solution

Flask API + CLI migration runner with:
- **4 modules:** `db.py` (SQLite layer), `files.py` (file parser), `runner.py` (core logic), `routes.py` (Flask API), `cli.py`
- **Migration files:** `NNNN_description.sql` with `-- migrate:up` / `-- migrate:down` markers
- **3 API routes:** `POST /migrate/up`, `POST /migrate/down`, `GET /migrate/status` + `DELETE /migrate/lock` admin endpoint
- **3 CLI commands:** `up [--dry-run] [--target VERSION]`, `down [--steps N] [--dry-run]`, `status`
- **Advisory lock:** `migrations_lock` table row, acquired with `BEGIN IMMEDIATE`
- **Dry-run:** SAVEPOINT-based execution + rollback within the lock transaction
- **Checksum verification:** SHA-256 of `up_sql` stored at apply time; mismatch blocks further operations

## Why This Approach

- **Advisory lock row vs. BEGIN EXCLUSIVE:** BEGIN EXCLUSIVE blocks all readers for the entire migration duration. Advisory row is explicit, observable, releasable on crash (admin DELETE endpoint), and doesn't block readers.
- **Directory scan vs. API registration:** API registration creates a circular dependency (migration scripts stored in the DB they migrate). Directory scan is the industry standard (Flyway, Alembic, golang-migrate).
- **Single-file `-- migrate:up`/`-- migrate:down` vs. separate files:** Two files per migration adds friction and makes co-review harder. Single-file is dbmate convention.
- **executescript() NEVER used:** `executescript()` issues an implicit COMMIT that releases the lock and breaks the atomic `mark_applied` step. Individual `conn.execute()` calls used instead.

## Risk Resolution

> **Flagged risk:** "Dry-run correctness for DDL in SQLite. SQLite DDL IS transactional, so wrapping in a transaction and rolling back should work. But if a migration mixes DDL + DML with triggers or virtual tables, the rollback behavior may surprise."

**What actually happened:** SQLite DDL rollback works correctly for `BEGIN IMMEDIATE` + `ROLLBACK`. The verify-first test (`test_migrator_dryrun.py`) confirmed: `CREATE TABLE` inside a `BEGIN IMMEDIATE` transaction is fully rolled back on `ROLLBACK`. The SAVEPOINT-based approach (`SAVEPOINT sp_dry` / `ROLLBACK TO SAVEPOINT sp_dry` / `RELEASE SAVEPOINT sp_dry`) also works correctly inside an outer `BEGIN IMMEDIATE` transaction.

**Lesson learned:** SQLite is genuinely transactional for DDL — the verify-first test resolved this uncertainty before a single route was written. The real surprise was the naive `str.split(';')` SQL splitter, which breaks on semicolons inside string literals. Use `sqlite3.complete_statement()` to walk statements correctly.

## Key Decisions

| Decision | Chosen | Rejected | Reason |
|----------|--------|----------|--------|
| Lock scope | Hold entire batch | Per-migration re-acquire | Per-migration has TOCTOU window between migrations |
| SQL splitting | `sqlite3.complete_statement()` | `str.split(';')` | Naive split breaks on semicolons in string literals |
| Dry-run mechanism | SAVEPOINT inside BEGIN IMMEDIATE | Separate read-only connection | SAVEPOINTs work inside BEGIN IMMEDIATE, verified by test |
| Lock on error | `with` block rollback cleans up | Explicit release before raise | Exceptions inside the `with` block auto-rollback, so explicit release is redundant and confusing |
| Migration isolation | SAVEPOINT per migration | Separate transaction per migration | Separate transactions require releasing the lock between them (TOCTOU); SAVEPOINTs within one transaction maintain lock throughout |

## Gotchas

- **Lock-per-migration is wrong:** The original implementation released the lock and re-acquired it for each migration, creating a TOCTOU window. Correct pattern: acquire once, run all migrations in SAVEPOINTs, release once. The `with get_db(immediate=True)` block commits on exit, atomically committing all applied records and releasing the lock.
- **`sqlite3.complete_statement()` for SQL parsing:** Any SQL migration with string literals or comments containing semicolons will break `str.split(';')`. Python's sqlite3 module exposes `sqlite3.complete_statement(fragment)` which correctly identifies statement boundaries.
- **`release_lock` inside `with get_db` block:** If `release_lock(conn)` is called before the `with` block exits and an exception occurs, the `with` block's `conn.rollback()` will undo the lock release — it was never committed. This means explicit `release_lock` before raising is unnecessary and confusing. Prefer letting the `with` block rollback handle cleanup. Only call `release_lock` on the happy path before the `with` block exits.
- **SAVEPOINT names must be unique per nesting level:** Using `sp_dry` and `sp_mig` as fixed names works because the dry-run and real-run paths never nest SAVEPOINTs.
- **Target validation before `init_db`:** Validate `target` version format before touching the DB to fail fast on bad input.
- **`executescript()` + WAL pragma ordering:** In `init_db`, set `PRAGMA journal_mode=WAL` before `executescript()` because `executescript()` issues an implicit COMMIT — WAL must be enabled before schema creation.

## Feed-Forward

- **Hardest decision:** Lock scope — per-migration vs. whole-batch. Whole-batch is correct but requires SAVEPOINTs for per-migration isolation. Per-migration seemed simpler but creates TOCTOU windows.
- **Rejected alternatives:** `str.split(';')` for SQL parsing (breaks on string literals); per-migration lock re-acquisition (TOCTOU); `BEGIN EXCLUSIVE` (blocks readers); executescript() inside transactions (implicit COMMIT).
- **Least confident:** The SAVEPOINT-within-BEGIN-IMMEDIATE pattern is correct in SQLite but may not work in other databases. If this runner is ever ported to PostgreSQL (which doesn't support DDL in regular transactions for some cases), the dry-run mechanism would need to change.
