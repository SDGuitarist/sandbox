---
title: "Database Migration Runner"
type: feat
status: active
date: 2026-04-05
origin: "docs/brainstorms/2026-04-05-db-migration-runner.md"
feed_forward:
  risk: "Dry-run correctness for DDL in SQLite. SQLite DDL IS transactional, so wrapping in a transaction and rolling back should work. But if a migration mixes DDL + DML with triggers or virtual tables, the rollback behavior may surprise. Need a verify-first test before implementing the dry-run path."
  verify_first: true
---

# feat: Database Migration Runner

## Enhancement Summary

**Deepened on:** 2026-04-05
**Research agents used:** solution-doc-searcher (prior cycle lessons)

### Key Corrections From Research
- `executescript()` must use raw `sqlite3.connect`, NOT `get_db` — executescript issues implicit COMMIT that bypasses context manager transaction semantics (from chat-room-api solution)
- All state-affecting computations must happen INSIDE BEGIN IMMEDIATE, not before (from task-scheduler solution)
- WAL mode + timeout mandatory for Flask+CLI concurrent access (from url-shortener solution)
- Merge check+write into single transaction to eliminate TOCTOU gaps (from chat-room-api solution)

## What Must Not Change

- The `schema_migrations` table schema once deployed — existing applied migration records must remain intact
- Migration file naming convention `NNNN_description.sql` — version ordering depends on it
- The up/down marker format `-- migrate:up` / `-- migrate:down` — user-authored migration files depend on it
- `get_db()` context manager semantics (WAL, row_factory, rollback on exception)
- Test isolation — each test gets its own tmp_path DB

## Prior Phase Risk

> "Dry-run correctness for DDL in SQLite. SQLite DDL IS transactional, so wrapping in a transaction and rolling back should work. But if a migration mixes DDL + DML with triggers or virtual tables, the rollback behavior may surprise."

**Response:** Write a verify-first test (`test_dry_run_ddl_rollback`) that:
1. Runs `migrate up --dry-run` on a migration that creates a table
2. Verifies the table does NOT exist after dry-run
3. Runs `migrate up` (for real)
4. Verifies the table DOES exist

This test must pass before implementing any routes or CLI commands.

## Smallest Safe Plan

### Phase 1: Core DB layer + verify-first dry-run test

**Files in scope:** `migrator/db.py`, `migrator/schema.sql`, `tests/test_migrator_dryrun.py`

**What to build:**
- `schema.sql`: `schema_migrations` and `migrations_lock` tables
- `get_db(path, immediate)` context manager (WAL, row_factory, BEGIN IMMEDIATE)
- `init_db(path)` using raw connection + executescript (NOT get_db)
- `acquire_lock(conn, locked_by)` — INSERT OR REPLACE into migrations_lock inside caller's BEGIN IMMEDIATE; raises `MigrationLockError` if already locked
- `release_lock(conn)` — DELETE from migrations_lock
- `get_applied(conn)` — SELECT version, name, applied_at, checksum from schema_migrations ORDER BY version
- `mark_applied(conn, version, name, up_sql)` — INSERT into schema_migrations with SHA-256 checksum
- `mark_rolled_back(conn, version)` — DELETE from schema_migrations
- Verify-first test: `test_dry_run_ddl_rollback` — confirms DDL rollback works in SQLite

**Gate:** Verify-first test passes before Phase 2 starts.

### Phase 2: Migration file parser + core migrate logic

**Files in scope:** `migrator/files.py`, `migrator/runner.py`, `tests/test_migrator_files.py`, `tests/test_migrator_runner.py`

**What to build:**
- `files.py`:
  - `parse_migration_file(path)` → `{version, name, up_sql, down_sql}` — splits on `-- migrate:down` marker
  - `load_migrations(migrations_dir)` → list of migration dicts sorted by version
  - `validate_version_format(version)` → raises `ValueError` if not 4-digit numeric string
- `runner.py`:
  - `migrate_up(db_path, migrations_dir, dry_run=False, target=None, locked_by="cli")` → `{applied: [versions], sql: [stmts], dry_run: bool}`
  - `migrate_down(db_path, migrations_dir, steps=1, dry_run=False, locked_by="cli")` → `{rolled_back: [versions], sql: [stmts], dry_run: bool}`
  - `migration_status(db_path, migrations_dir)` → `{applied: [...], pending: [...], missing: [...]}`
  - Each migrate_up/down: acquire lock → collect migrations → for each, execute SQL in a transaction → mark applied/rolled-back → release lock
  - Dry-run: BEGIN, execute SQL, collect statements list, ROLLBACK — do NOT call mark_applied/mark_rolled_back
  - Checksum verification: before running down, verify checksum of up_sql matches stored value; raise `ChecksumMismatchError` if tampered
  
**Gate:** All runner tests pass, including checksum mismatch and lock contention tests.

### Phase 3: Flask API routes

**Files in scope:** `migrator/routes.py`, `migrator/app.py`, `run_migrator.py`, `tests/test_migrator_routes.py`

**What to build:**
- `POST /migrate/up` — body: `{dry_run?: bool, target?: str}` → 200 with result dict
- `POST /migrate/down` — body: `{dry_run?: bool, steps?: int}` → 200 with result dict
- `GET /migrate/status` — 200 with status dict
- All routes read `db_path` from `current_app.config.get("DB_PATH")` and `migrations_dir` from `current_app.config.get("MIGRATIONS_DIR")`
- 409 if lock is held; 500 with error message on unexpected failures
- `create_app(db_path, migrations_dir)` factory

### Phase 4: CLI

**Files in scope:** `migrator/cli.py`

**What to build:**
- `python -m migrator.cli up [--dry-run] [--target VERSION] [--db PATH] [--dir PATH]`
- `python -m migrator.cli down [--steps N] [--dry-run] [--db PATH] [--dir PATH]`
- `python -m migrator.cli status [--db PATH] [--dir PATH]`
- Reads `MIGRATIONS_DB` and `MIGRATIONS_DIR` env vars as defaults
- Exits 0 on success, 1 on error, 2 on lock contention

## Rejected Options

- **API-based registration (POST migration SQL):** Circular — storing migration scripts in the DB they're supposed to migrate. Not reviewable as code. Rejected.
- **BEGIN EXCLUSIVE for locking:** Blocks all reads during migration. Advisory lock row is less invasive and observable.
- **Separate up/down files:** Two files per migration, harder to keep in sync. Single-file with markers is standard (dbmate convention).
- **Recursive migration execution:** Each migration runs in its own transaction for isolation. If one fails, prior ones stay applied (like real migration runners).

## Risks And Unknowns

1. **SQLite DDL rollback:** DDL in SQLite is transactional — but test it first (verify-first gate).
2. **Lock stale on crash:** If the migration process crashes, the lock row stays. Add a `locked_at` timestamp; if `locked_at < now - 10min`, consider it stale. For this MVP, add a `DELETE /migrate/lock` admin endpoint to force-release.
3. **`executescript()` for multi-statement migrations:** `conn.executescript(up_sql)` issues implicit COMMIT — use `conn.executemany` or split statements and execute individually. For dry-run, split and execute in a regular transaction.
4. **Migration file modification:** If an applied migration file changes on disk (checksum mismatch), block operations and report which version was tampered.
5. **Empty down_sql:** Migrations without a `-- migrate:down` section cannot be rolled back — return 409 with explanation.

## Most Likely Way This Plan Is Wrong

The `executescript()` footgun in Phase 2: if `migrate_up` calls `conn.executescript(up_sql)` inside a transaction, the implicit COMMIT will release the lock and the apply-to-schema_migrations INSERT will be outside the intended transaction. Must use individual `conn.execute()` calls (after splitting on `;`) or `conn.executemany()` — never `executescript()` inside a managed transaction.

## Scope Creep Check

Compared to brainstorm: everything in this plan was in the brainstorm. Not adding:
- Migration generation (CREATE FILE command) — deferred
- Multiple DB support — deferred
- PostgreSQL/MySQL — deferred (SQLite only)
- `--fake` flag (mark as applied without running) — deferred

## Acceptance Criteria

- [ ] `migrate up` applies all pending migrations in version order
- [ ] `migrate up --target 0002` stops after applying version 0002
- [ ] `migrate down` rolls back the most recently applied migration
- [ ] `migrate down --steps 2` rolls back the last 2 applied migrations
- [ ] `migrate status` shows applied, pending, and missing migrations
- [ ] `migrate up --dry-run` returns SQL that would run without applying changes (table not created)
- [ ] `migrate down --dry-run` returns SQL that would run without rolling back
- [ ] Two concurrent `migrate up` calls: second returns 409 lock contention
- [ ] Modified applied migration (checksum mismatch) blocks further migrations with a clear error
- [ ] Migration with no `-- migrate:down` section returns 409 on down attempt
- [ ] `POST /migrate/up`, `POST /migrate/down`, `GET /migrate/status` routes return correct results
- [ ] CLI exits 0 on success, 1 on error, 2 on lock contention
- [ ] All migrations applied in a single `migrate up` run are applied atomically per-migration (each in its own transaction; prior successes persist on failure)
- [ ] Verify-first test passes: DDL rolled back in dry-run, DDL committed in real run

## Tests Or Checks

```bash
pytest tests/test_migrator_dryrun.py -v    # verify-first gate
pytest tests/test_migrator_files.py -v
pytest tests/test_migrator_runner.py -v
pytest tests/test_migrator_routes.py -v
pytest tests/ -v                            # full suite
```

## Rollback Plan

All new files under `migrator/`. No existing files modified. To undo: `rm -rf migrator/ tests/test_migrator_*.py run_migrator.py`.

## Claude Code Handoff Prompt

```text
Read docs/plans/2026-04-05-feat-db-migration-runner-plan.md.

PREREQUISITE: Write and pass tests/test_migrator_dryrun.py (verify-first DDL rollback test) before implementing routes or CLI.

Repos and files in scope:
- migrator/schema.sql
- migrator/db.py
- migrator/files.py
- migrator/runner.py
- migrator/routes.py
- migrator/app.py
- migrator/cli.py
- run_migrator.py
- tests/test_migrator_dryrun.py
- tests/test_migrator_files.py
- tests/test_migrator_runner.py
- tests/test_migrator_routes.py

Scope boundaries:
- SQLite only — no PostgreSQL/MySQL
- No migration file generation command
- No --fake flag
- schema_migrations and migrations_lock tables are in the same DB being migrated
- executescript() must NEVER be used inside a managed transaction (implicit COMMIT footgun)

Key corrections from plan review: [fill after Codex review]

Acceptance criteria:
- migrate up applies all pending in order
- migrate up --target stops at version
- migrate down rolls back N steps (default 1)
- migrate status shows applied/pending/missing
- dry-run returns SQL without applying, DDL rolled back
- concurrent up returns 409
- checksum mismatch blocks with clear error
- no down_sql returns 409
- Flask routes: POST /migrate/up, POST /migrate/down, GET /migrate/status
- CLI exits 0/1/2

Required checks:
pytest tests/ -v

Stop conditions:
- If executescript() is needed inside a transaction, STOP and ask — use individual execute() calls instead
- If SQLite DDL rollback fails in verify-first test, STOP and report
```

## Sources

- Brainstorm: docs/brainstorms/2026-04-05-db-migration-runner.md

## Feed-Forward

- **Hardest decision:** Lock strategy — advisory lock row (chosen) vs BEGIN EXCLUSIVE. Advisory row is observable, releasable, and doesn't block readers. BEGIN EXCLUSIVE would lock the entire DB for the duration of all migrations.
- **Rejected alternatives:** API-based migration registration (circular); BEGIN EXCLUSIVE locking (too aggressive); separate up/down files (two-file management friction); executescript() inside transactions (implicit COMMIT footgun).
- **Least confident:** executescript() footgun in Phase 2 migration execution. Using `conn.executescript(up_sql)` inside a BEGIN IMMEDIATE transaction commits the transaction immediately, releasing the lock and breaking the atomic mark_applied step. Must split SQL on `;` and use individual `conn.execute()` calls. Verify this works for multi-statement migrations.
