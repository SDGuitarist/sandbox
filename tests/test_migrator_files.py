"""Tests for migration file parsing and loading."""
import pytest
from pathlib import Path

from migrator.files import (
    MigrationFileError,
    load_migrations,
    parse_migration_file,
    validate_version_format,
)


def write_migration(tmp_path, filename, content):
    f = tmp_path / filename
    f.write_text(content)
    return f


# ── validate_version_format ───────────────────────────────────────────────────

def test_valid_version():
    validate_version_format("0001")
    validate_version_format("9999")


def test_invalid_version_letters():
    with pytest.raises(ValueError):
        validate_version_format("abcd")


def test_invalid_version_too_short():
    with pytest.raises(ValueError):
        validate_version_format("001")


def test_invalid_version_too_long():
    with pytest.raises(ValueError):
        validate_version_format("00001")


# ── parse_migration_file ──────────────────────────────────────────────────────

def test_parse_basic_up_and_down(tmp_path):
    f = write_migration(tmp_path, "0001_create_users.sql", """
-- migrate:up
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);

-- migrate:down
DROP TABLE users;
""")
    m = parse_migration_file(f)
    assert m["version"] == "0001"
    assert m["name"] == "create_users"
    assert "CREATE TABLE users" in m["up_sql"]
    assert "DROP TABLE users" in m["down_sql"]


def test_parse_no_down_section(tmp_path):
    f = write_migration(tmp_path, "0002_add_index.sql", """
-- migrate:up
CREATE INDEX idx_users_name ON users(name);
""")
    m = parse_migration_file(f)
    assert m["down_sql"] == ""


def test_parse_missing_up_marker(tmp_path):
    f = write_migration(tmp_path, "0003_bad.sql", "CREATE TABLE foo (id INTEGER);")
    with pytest.raises(MigrationFileError, match="missing '-- migrate:up'"):
        parse_migration_file(f)


def test_parse_empty_up_sql(tmp_path):
    f = write_migration(tmp_path, "0004_empty.sql", "-- migrate:up\n\n-- migrate:down\nDROP TABLE x;")
    with pytest.raises(MigrationFileError, match="empty up_sql"):
        parse_migration_file(f)


def test_parse_bad_filename(tmp_path):
    f = write_migration(tmp_path, "bad_name.sql", "-- migrate:up\nSELECT 1;")
    with pytest.raises(MigrationFileError, match="must match NNNN_description"):
        parse_migration_file(f)


def test_parse_multi_statement_up(tmp_path):
    f = write_migration(tmp_path, "0005_multi.sql", """
-- migrate:up
CREATE TABLE a (id INTEGER PRIMARY KEY);
CREATE TABLE b (id INTEGER PRIMARY KEY);

-- migrate:down
DROP TABLE b;
DROP TABLE a;
""")
    m = parse_migration_file(f)
    assert "CREATE TABLE a" in m["up_sql"]
    assert "CREATE TABLE b" in m["up_sql"]


# ── load_migrations ───────────────────────────────────────────────────────────

def test_load_migrations_sorted(tmp_path):
    write_migration(tmp_path, "0003_third.sql", "-- migrate:up\nSELECT 3;")
    write_migration(tmp_path, "0001_first.sql", "-- migrate:up\nSELECT 1;")
    write_migration(tmp_path, "0002_second.sql", "-- migrate:up\nSELECT 2;")
    migrations = load_migrations(tmp_path)
    assert [m["version"] for m in migrations] == ["0001", "0002", "0003"]


def test_load_migrations_empty_dir(tmp_path):
    assert load_migrations(tmp_path) == []


def test_load_migrations_ignores_non_sql(tmp_path):
    (tmp_path / "README.md").write_text("docs")
    (tmp_path / "0001_init.sql").write_text("-- migrate:up\nSELECT 1;")
    migrations = load_migrations(tmp_path)
    assert len(migrations) == 1


def test_load_migrations_missing_dir():
    with pytest.raises(MigrationFileError, match="does not exist"):
        load_migrations("/nonexistent/path")
