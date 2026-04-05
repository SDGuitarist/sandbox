"""Tests for the migration runner (up, down, status, dry-run, locking, checksums)."""
import sqlite3
import pytest

from migrator.db import ChecksumMismatchError, MigrationLockError, init_db, get_db, acquire_lock
from migrator.runner import migrate_up, migrate_down, migration_status


def write_migration(migrations_dir, filename, content):
    f = migrations_dir / filename
    f.write_text(content)
    return f


@pytest.fixture
def env(tmp_path):
    db_path = str(tmp_path / "test.db")
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    return db_path, migrations_dir


# ── migrate_up ────────────────────────────────────────────────────────────────

def test_split_sql_handles_semicolon_in_string(env):
    """_split_sql must not split on semicolons inside string literals."""
    from migrator.runner import _split_sql
    sql = "INSERT INTO config VALUES ('key', 'value; with semicolon');\nINSERT INTO config VALUES ('k2', 'fine');"
    stmts = _split_sql(sql)
    assert len(stmts) == 2
    assert "value; with semicolon" in stmts[0]


def test_migrate_up_applies_pending(env):
    db_path, md = env
    write_migration(md, "0001_create_users.sql",
        "-- migrate:up\nCREATE TABLE users (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE users;")
    result = migrate_up(db_path, md)
    assert result["applied"] == ["0001"]
    assert result["dry_run"] is False
    # Table should exist
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT name FROM sqlite_master WHERE name='users'").fetchone()
    conn.close()
    assert row is not None


def test_migrate_up_idempotent(env):
    db_path, md = env
    write_migration(md, "0001_init.sql", "-- migrate:up\nCREATE TABLE t1 (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t1;")
    migrate_up(db_path, md)
    result = migrate_up(db_path, md)
    assert result["applied"] == []


def test_migrate_up_applies_in_order(env):
    db_path, md = env
    write_migration(md, "0002_second.sql", "-- migrate:up\nCREATE TABLE t2 (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t2;")
    write_migration(md, "0001_first.sql", "-- migrate:up\nCREATE TABLE t1 (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t1;")
    result = migrate_up(db_path, md)
    assert result["applied"] == ["0001", "0002"]


def test_migrate_up_invalid_target_format(env):
    db_path, md = env
    with pytest.raises(ValueError, match="Invalid migration version"):
        migrate_up(db_path, md, target="abc")


def test_migrate_up_with_target(env):
    db_path, md = env
    write_migration(md, "0001_a.sql", "-- migrate:up\nCREATE TABLE a (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE a;")
    write_migration(md, "0002_b.sql", "-- migrate:up\nCREATE TABLE b (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE b;")
    write_migration(md, "0003_c.sql", "-- migrate:up\nCREATE TABLE c (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE c;")
    result = migrate_up(db_path, md, target="0002")
    assert result["applied"] == ["0001", "0002"]
    # 0003 still pending
    status = migration_status(db_path, md)
    assert any(p["version"] == "0003" for p in status["pending"])


# ── migrate_up dry-run ────────────────────────────────────────────────────────

def test_migrate_up_dry_run(env):
    db_path, md = env
    write_migration(md, "0001_create.sql",
        "-- migrate:up\nCREATE TABLE dry_t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE dry_t;")
    result = migrate_up(db_path, md, dry_run=True)
    assert result["dry_run"] is True
    assert result["applied"] == ["0001"]
    assert "CREATE TABLE dry_t" in result["sql"]["0001"][0]
    # Table must NOT exist
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT name FROM sqlite_master WHERE name='dry_t'").fetchone()
    conn.close()
    assert row is None


def test_migrate_up_dry_run_does_not_record_applied(env):
    db_path, md = env
    write_migration(md, "0001_x.sql", "-- migrate:up\nCREATE TABLE x (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE x;")
    migrate_up(db_path, md, dry_run=True)
    status = migration_status(db_path, md)
    assert len(status["applied"]) == 0
    assert len(status["pending"]) == 1


# ── migrate_down ──────────────────────────────────────────────────────────────

def test_migrate_down_rolls_back_one(env):
    db_path, md = env
    write_migration(md, "0001_t.sql",
        "-- migrate:up\nCREATE TABLE t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t;")
    migrate_up(db_path, md)
    result = migrate_down(db_path, md)
    assert result["rolled_back"] == ["0001"]
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT name FROM sqlite_master WHERE name='t'").fetchone()
    conn.close()
    assert row is None


def test_migrate_down_steps(env):
    db_path, md = env
    write_migration(md, "0001_a.sql",
        "-- migrate:up\nCREATE TABLE a (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE a;")
    write_migration(md, "0002_b.sql",
        "-- migrate:up\nCREATE TABLE b (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE b;")
    write_migration(md, "0003_c.sql",
        "-- migrate:up\nCREATE TABLE c (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE c;")
    migrate_up(db_path, md)
    result = migrate_down(db_path, md, steps=2)
    assert result["rolled_back"] == ["0003", "0002"]


def test_migrate_down_no_applied(env):
    db_path, md = env
    result = migrate_down(db_path, md)
    assert result["rolled_back"] == []


def test_migrate_down_no_down_sql_raises(env):
    db_path, md = env
    write_migration(md, "0001_nodwn.sql", "-- migrate:up\nCREATE TABLE nd (id INTEGER PRIMARY KEY);")
    migrate_up(db_path, md)
    with pytest.raises(ValueError, match="no down SQL"):
        migrate_down(db_path, md)


def test_migrate_down_dry_run(env):
    db_path, md = env
    write_migration(md, "0001_t.sql",
        "-- migrate:up\nCREATE TABLE t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t;")
    migrate_up(db_path, md)
    result = migrate_down(db_path, md, dry_run=True)
    assert result["dry_run"] is True
    assert result["rolled_back"] == ["0001"]
    # Table still exists
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT name FROM sqlite_master WHERE name='t'").fetchone()
    conn.close()
    assert row is not None


# ── checksum ──────────────────────────────────────────────────────────────────

def test_checksum_mismatch_blocks_up(env):
    db_path, md = env
    f = write_migration(md, "0001_t.sql",
        "-- migrate:up\nCREATE TABLE t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t;")
    migrate_up(db_path, md)
    # Tamper with the file
    f.write_text("-- migrate:up\nCREATE TABLE tampered (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE tampered;")
    with pytest.raises(ChecksumMismatchError):
        migrate_up(db_path, md)


def test_checksum_mismatch_blocks_down(env):
    db_path, md = env
    f = write_migration(md, "0001_t.sql",
        "-- migrate:up\nCREATE TABLE t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t;")
    migrate_up(db_path, md)
    f.write_text("-- migrate:up\nCREATE TABLE tampered (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE tampered;")
    with pytest.raises(ChecksumMismatchError):
        migrate_down(db_path, md)


# ── lock ──────────────────────────────────────────────────────────────────────

def test_lock_prevents_concurrent_up(env):
    db_path, md = env
    write_migration(md, "0001_t.sql",
        "-- migrate:up\nCREATE TABLE t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t;")
    init_db(db_path)
    # Simulate a stale lock left by a crashed process (committed lock row)
    with get_db(path=db_path, immediate=True) as conn:
        acquire_lock(conn, "other-process")
    # Lock is now committed — migrate_up should see it and raise MigrationLockError
    with pytest.raises(MigrationLockError, match="other-process"):
        migrate_up(db_path, md)


# ── status ────────────────────────────────────────────────────────────────────

def test_status_empty(env):
    db_path, md = env
    status = migration_status(db_path, md)
    assert status == {"applied": [], "pending": [], "missing": []}


def test_status_after_partial_up(env):
    db_path, md = env
    write_migration(md, "0001_a.sql",
        "-- migrate:up\nCREATE TABLE a (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE a;")
    write_migration(md, "0002_b.sql",
        "-- migrate:up\nCREATE TABLE b (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE b;")
    migrate_up(db_path, md, target="0001")
    status = migration_status(db_path, md)
    assert len(status["applied"]) == 1
    assert status["applied"][0]["version"] == "0001"
    assert len(status["pending"]) == 1
    assert status["pending"][0]["version"] == "0002"
    assert status["missing"] == []


def test_status_missing_file(env):
    db_path, md = env
    f = write_migration(md, "0001_a.sql",
        "-- migrate:up\nCREATE TABLE a (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE a;")
    migrate_up(db_path, md)
    f.unlink()  # delete the file after applying
    status = migration_status(db_path, md)
    assert len(status["missing"]) == 1
    assert status["missing"][0]["version"] == "0001"
