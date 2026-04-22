"""Tests for CSV import functionality."""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db, init_db
from ingest import import_from_csv


def _temp_db(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    return db


def _write_csv(tmp_path, filename, headers, rows):
    path = tmp_path / filename
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(path)


def test_import_basic_csv(tmp_path):
    db = _temp_db(tmp_path)
    csv_path = _write_csv(tmp_path, "leads.csv", ["name", "profile_url"], [
        {"name": "Alice", "profile_url": "https://facebook.com/alice"},
        {"name": "Bob", "profile_url": "https://facebook.com/bob"},
    ])
    inserted, skipped, rejected = import_from_csv(csv_path, db_path=db)
    assert inserted == 2
    assert skipped == 0
    assert rejected == 0


def test_import_flexible_headers(tmp_path):
    db = _temp_db(tmp_path)
    csv_path = _write_csv(tmp_path, "leads.csv", ["Name", "Profile URL", "Bio"], [
        {"Name": "Alice", "Profile URL": "https://facebook.com/alice", "Bio": "Writer"},
    ])
    inserted, _, _ = import_from_csv(csv_path, db_path=db)
    assert inserted == 1
    with get_db(db) as conn:
        row = conn.execute("SELECT bio FROM leads WHERE name = 'Alice'").fetchone()
    assert row["bio"] == "Writer"


def test_import_ignores_phone_column(tmp_path):
    """phone is not in ingest_leads INSERT path -- should be silently ignored."""
    db = _temp_db(tmp_path)
    csv_path = _write_csv(tmp_path, "leads.csv", ["name", "profile_url", "phone"], [
        {"name": "Alice", "profile_url": "https://facebook.com/alice", "phone": "619-555-1234"},
    ])
    inserted, _, _ = import_from_csv(csv_path, db_path=db)
    assert inserted == 1
    with get_db(db) as conn:
        row = conn.execute("SELECT phone FROM leads WHERE name = 'Alice'").fetchone()
    # phone should be NULL because ingest_leads doesn't write it
    assert row["phone"] is None


def test_import_skips_missing_name(tmp_path):
    db = _temp_db(tmp_path)
    csv_path = _write_csv(tmp_path, "leads.csv", ["name", "profile_url"], [
        {"name": "", "profile_url": "https://facebook.com/noname"},
        {"name": "Valid", "profile_url": "https://facebook.com/valid"},
    ])
    inserted, skipped, rejected = import_from_csv(csv_path, db_path=db)
    assert inserted == 1
    assert rejected == 1


def test_import_dedup(tmp_path):
    db = _temp_db(tmp_path)
    csv_path = _write_csv(tmp_path, "leads.csv", ["name", "profile_url"], [
        {"name": "Alice", "profile_url": "https://facebook.com/alice"},
        {"name": "Alice Dup", "profile_url": "https://facebook.com/alice"},
    ])
    inserted, skipped, rejected = import_from_csv(csv_path, db_path=db)
    assert inserted == 1
    assert skipped == 1


def test_import_auto_fixes_facebook_id(tmp_path):
    db = _temp_db(tmp_path)
    csv_path = _write_csv(tmp_path, "leads.csv", ["name", "profile_url"], [
        {"name": "Alice", "profile_url": "123456789"},
    ])
    inserted, _, _ = import_from_csv(csv_path, db_path=db)
    assert inserted == 1
    with get_db(db) as conn:
        row = conn.execute("SELECT profile_url FROM leads WHERE name = 'Alice'").fetchone()
    assert row["profile_url"] == "https://www.facebook.com/123456789"


def test_import_rejects_invalid_url(tmp_path):
    db = _temp_db(tmp_path)
    csv_path = _write_csv(tmp_path, "leads.csv", ["name", "profile_url"], [
        {"name": "Alice", "profile_url": "not-a-url"},
    ])
    inserted, _, rejected = import_from_csv(csv_path, db_path=db)
    assert inserted == 0
    assert rejected == 1
