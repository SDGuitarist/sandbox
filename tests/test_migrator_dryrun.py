"""Verify-first: SQLite DDL is transactional — dry-run can roll back CREATE TABLE."""
import sqlite3
import pytest

from migrator.db import init_db


def _table_exists(db_path, table_name):
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def test_dry_run_ddl_rollback(tmp_path):
    """DDL inside a rolled-back transaction must not persist."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    try:
        # Use BEGIN IMMEDIATE to match production semantics exactly
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("CREATE TABLE dry_run_table (id INTEGER PRIMARY KEY)")
        # Verify it exists inside the transaction
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dry_run_table'"
        ).fetchone()
        assert row is not None, "Table should be visible inside transaction"
        conn.rollback()
    finally:
        conn.close()

    # After rollback the table must not exist
    assert not _table_exists(db_path, "dry_run_table"), (
        "DDL rollback failed — SQLite may not support transactional DDL here"
    )


def test_real_run_ddl_persists(tmp_path):
    """DDL inside a committed transaction must persist."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN")
        conn.execute("CREATE TABLE real_table (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()

    assert _table_exists(db_path, "real_table"), "DDL commit failed"


def test_dry_run_multiple_statements(tmp_path):
    """Multiple DDL statements in a rolled-back transaction all disappear."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN")
        conn.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE t2 (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO t1 VALUES (1)")
        conn.rollback()
    finally:
        conn.close()

    assert not _table_exists(db_path, "t1")
    assert not _table_exists(db_path, "t2")
