"""Core migration execution logic.

Key design decisions:
- Lock is held for the ENTIRE batch (acquire once, run all, release once). This prevents
  TOCTOU windows where another process could slip between migrations in a batch.
- Each migration runs in its own SAVEPOINT for per-migration isolation. If migration N fails,
  migrations 0..N-1 remain applied (their SAVEPOINTs were released/committed to the outer tx).
- Dry-run: execute SQL in SAVEPOINTs, collect statements, then ROLLBACK each SAVEPOINT.
  The outer BEGIN IMMEDIATE is then rolled back on exit (lock never commits).
- executescript() is NEVER used — it issues an implicit COMMIT that would release the lock.
  SQL is split using sqlite3.complete_statement() to handle semicolons in string literals.
"""
import sqlite3

from .db import (
    ChecksumMismatchError,
    MigrationLockError,
    acquire_lock,
    checksum,
    get_applied,
    get_db,
    init_db,
    mark_applied,
    mark_rolled_back,
    release_lock,
)
from .files import load_migrations


def _split_sql(sql: str) -> list[str]:
    """Split SQL into individual statements using sqlite3.complete_statement().

    This correctly handles semicolons inside string literals and comments,
    unlike naive str.split(';').
    """
    stmts = []
    current = []
    for char in sql:
        current.append(char)
        fragment = "".join(current)
        if sqlite3.complete_statement(fragment):
            stripped = fragment.strip()
            # Remove trailing semicolon for cleaner display, but the statement
            # is valid with or without it for conn.execute()
            if stripped:
                stmts.append(stripped.rstrip(";").strip())
            current = []
    # Handle any trailing content without a final semicolon
    remainder = "".join(current).strip()
    if remainder:
        stmts.append(remainder)
    return [s for s in stmts if s]


def _execute_sql_statements(conn, sql: str) -> list[str]:
    """Execute SQL statements one by one. Returns list of executed statements."""
    stmts = _split_sql(sql)
    for stmt in stmts:
        conn.execute(stmt)
    return stmts


def migrate_up(db_path, migrations_dir, dry_run=False, target=None, locked_by="cli") -> dict:
    """Apply all pending migrations (up to target if specified).

    Holds the advisory lock for the entire batch to prevent TOCTOU windows.
    Each migration runs in its own SAVEPOINT — a failure stops the batch but
    leaves prior migrations applied.

    Returns:
        {applied: [versions], sql: {version: [stmts]}, dry_run: bool}

    Raises:
        MigrationLockError: if another migration is running
        ChecksumMismatchError: if an applied migration file was modified on disk
        ValueError: if target version format is invalid
    """
    if target is not None:
        from .files import validate_version_format
        validate_version_format(target)

    init_db(db_path)
    all_migrations = load_migrations(migrations_dir)

    result = {"applied": [], "sql": {}, "dry_run": dry_run}

    with get_db(path=db_path, immediate=True) as conn:
        acquire_lock(conn, locked_by)

        applied_rows = get_applied(conn)
        applied_versions = {r["version"]: r for r in applied_rows}

        # Verify checksums for already-applied migrations
        for migration in all_migrations:
            v = migration["version"]
            if v in applied_versions:
                stored = applied_versions[v]["checksum"]
                actual = checksum(migration["up_sql"])
                if stored != actual:
                    # Let the with-block rollback handle lock cleanup
                    raise ChecksumMismatchError(
                        f"Migration {v} ('{migration['name']}') was modified after being applied. "
                        f"Expected checksum {stored[:8]}…, got {actual[:8]}…"
                    )

        # Determine pending migrations
        pending = [m for m in all_migrations if m["version"] not in applied_versions]
        if target:
            pending = [m for m in pending if m["version"] <= target]

        if not pending:
            release_lock(conn)
            return result

        if dry_run:
            # Execute each migration in a SAVEPOINT, collect SQL, rollback the SAVEPOINT.
            # On exception: clear partial results so caller gets either all-or-nothing.
            for migration in pending:
                conn.execute("SAVEPOINT sp_dry")
                try:
                    stmts = _execute_sql_statements(conn, migration["up_sql"])
                    conn.execute("ROLLBACK TO SAVEPOINT sp_dry")
                    conn.execute("RELEASE SAVEPOINT sp_dry")
                except Exception:
                    conn.execute("ROLLBACK TO SAVEPOINT sp_dry")
                    conn.execute("RELEASE SAVEPOINT sp_dry")
                    result["applied"].clear()
                    result["sql"].clear()
                    raise
                result["applied"].append(migration["version"])
                result["sql"][migration["version"]] = stmts
            release_lock(conn)
            return result

        # Real run: each migration in its own SAVEPOINT.
        # Lock is held for the entire batch — no inter-migration window.
        for migration in pending:
            conn.execute("SAVEPOINT sp_mig")
            try:
                stmts = _execute_sql_statements(conn, migration["up_sql"])
                mark_applied(conn, migration["version"], migration["name"], migration["up_sql"])
                conn.execute("RELEASE SAVEPOINT sp_mig")
            except Exception:
                conn.execute("ROLLBACK TO SAVEPOINT sp_mig")
                conn.execute("RELEASE SAVEPOINT sp_mig")
                release_lock(conn)
                raise
            result["applied"].append(migration["version"])
            result["sql"][migration["version"]] = stmts

        release_lock(conn)

    return result


def migrate_down(db_path, migrations_dir, steps=1, dry_run=False, locked_by="cli") -> dict:
    """Roll back the last N applied migrations.

    Holds the advisory lock for the entire batch.

    Returns:
        {rolled_back: [versions], sql: {version: [stmts]}, dry_run: bool}

    Raises:
        MigrationLockError: if another migration is running
        ChecksumMismatchError: if an applied migration file was modified on disk
        ValueError: if a migration has no down_sql or the file is missing
    """
    init_db(db_path)
    all_migrations = load_migrations(migrations_dir)
    migration_map = {m["version"]: m for m in all_migrations}

    result = {"rolled_back": [], "sql": {}, "dry_run": dry_run}

    with get_db(path=db_path, immediate=True) as conn:
        acquire_lock(conn, locked_by)
        applied_rows = get_applied(conn)

        if not applied_rows:
            release_lock(conn)
            return result

        # Roll back in reverse order (most recent first)
        to_rollback = list(reversed(applied_rows))[:steps]

        # Validate everything before executing anything
        for row in to_rollback:
            v = row["version"]
            if v not in migration_map:
                raise ValueError(
                    f"Cannot roll back migration {v}: file not found in migrations directory"
                )
            migration = migration_map[v]
            actual = checksum(migration["up_sql"])
            if row["checksum"] != actual:
                raise ChecksumMismatchError(
                    f"Migration {v} ('{migration['name']}') was modified after being applied."
                )
            if not migration["down_sql"]:
                raise ValueError(
                    f"Migration {v} ('{migration['name']}') has no down SQL — cannot roll back"
                )

        if dry_run:
            for row in to_rollback:
                migration = migration_map[row["version"]]
                conn.execute("SAVEPOINT sp_dry")
                try:
                    stmts = _execute_sql_statements(conn, migration["down_sql"])
                    conn.execute("ROLLBACK TO SAVEPOINT sp_dry")
                    conn.execute("RELEASE SAVEPOINT sp_dry")
                except Exception:
                    conn.execute("ROLLBACK TO SAVEPOINT sp_dry")
                    conn.execute("RELEASE SAVEPOINT sp_dry")
                    result["rolled_back"].clear()
                    result["sql"].clear()
                    raise
                result["rolled_back"].append(row["version"])
                result["sql"][row["version"]] = stmts
            release_lock(conn)
            return result

        # Real rollback: each in its own SAVEPOINT, lock held for entire batch
        for row in to_rollback:
            migration = migration_map[row["version"]]
            conn.execute("SAVEPOINT sp_mig")
            try:
                stmts = _execute_sql_statements(conn, migration["down_sql"])
                mark_rolled_back(conn, row["version"])
                conn.execute("RELEASE SAVEPOINT sp_mig")
            except Exception:
                conn.execute("ROLLBACK TO SAVEPOINT sp_mig")
                conn.execute("RELEASE SAVEPOINT sp_mig")
                release_lock(conn)
                raise
            result["rolled_back"].append(row["version"])
            result["sql"][row["version"]] = stmts

        release_lock(conn)

    return result


def migration_status(db_path, migrations_dir) -> dict:
    """Return status of all migrations.

    Returns:
        {
            applied: [{version, name, applied_at}],
            pending: [{version, name}],
            missing: [{version, name}]   # applied but file no longer exists
        }
    """
    init_db(db_path)
    all_migrations = load_migrations(migrations_dir)
    file_versions = {m["version"]: m for m in all_migrations}

    with get_db(path=db_path) as conn:
        applied_rows = get_applied(conn)

    applied_versions = {r["version"] for r in applied_rows}

    applied = [
        {"version": r["version"], "name": r["name"], "applied_at": r["applied_at"]}
        for r in applied_rows
    ]
    pending = [
        {"version": m["version"], "name": m["name"]}
        for m in all_migrations
        if m["version"] not in applied_versions
    ]
    missing = [
        {"version": r["version"], "name": r["name"]}
        for r in applied_rows
        if r["version"] not in file_versions
    ]

    return {"applied": applied, "pending": pending, "missing": missing}
