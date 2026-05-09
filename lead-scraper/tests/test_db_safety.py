"""Regression tests for production database safety."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import db as db_module
from app import create_app


def _create_legacy_campaign_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE leads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            profile_url TEXT NOT NULL,
            source      TEXT NOT NULL,
            UNIQUE(source, profile_url)
        );

        CREATE TABLE campaigns (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT NOT NULL,
            target_date       TEXT,
            segment_filter    TEXT,
            template_vars_json TEXT,
            created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
        );

        CREATE TABLE outreach_queue (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
            campaign_id     INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            opener_text     TEXT,
            template_text   TEXT,
            full_message    TEXT,
            status          TEXT NOT NULL DEFAULT 'draft'
                            CHECK(status IN ('draft', 'approved', 'sent', 'skipped',
                                             'replied', 'booked', 'declined', 'no_response')),
            generated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
            approved_at     TEXT,
            sent_at         TEXT,
            UNIQUE(lead_id, campaign_id)
        );
    """)
    conn.executemany(
        "INSERT INTO leads (id, name, profile_url, source) VALUES (?, ?, ?, ?)",
        [
            (1, "Alice", "https://example.com/alice", "test"),
            (2, "Bob", "https://example.com/bob", "test"),
        ],
    )
    conn.execute("INSERT INTO campaigns (id, name) VALUES (1, 'Workshop')")
    conn.executemany(
        """
        INSERT INTO outreach_queue
            (id, lead_id, campaign_id, opener_text, template_text, full_message, status)
        VALUES (?, ?, 1, ?, ?, ?, ?)
        """,
        [
            (1, 1, "Hi Alice", "Template A", "Full A", "draft"),
            (2, 2, "Hi Bob", "Template B", "Full B", "approved"),
        ],
    )
    conn.commit()
    conn.close()


def _count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    value = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return value


def test_pytest_cannot_open_production_db_path(monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_db_safety.py::guard")

    with pytest.raises(db_module.MigrationSafetyError):
        db_module.init_db(db_module.DB_PATH)

    with pytest.raises(db_module.MigrationSafetyError):
        with db_module.get_db(db_module.DB_PATH):
            pass


def test_create_app_accepts_temp_db_under_pytest(tmp_path):
    app = create_app(tmp_path / "app.db")
    app.config["TESTING"] = True

    response = app.test_client().get("/")

    assert response.status_code == 200


def test_init_db_preserves_existing_temp_data(tmp_path):
    db_path = tmp_path / "current.db"
    db_module.init_db(db_path)
    with db_module.get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO leads (id, name, profile_url, source) VALUES (1, 'Alice', 'https://example.com/a', 'test')"
        )
        conn.execute("INSERT INTO campaigns (id, name) VALUES (1, 'Workshop')")
        conn.execute(
            """
            INSERT INTO outreach_queue
                (id, lead_id, campaign_id, opener_text, template_text, full_message, status)
            VALUES (1, 1, 1, 'Hi', 'Template', 'Full', 'draft')
            """
        )

    db_module.init_db(db_path)

    assert _count(db_path, "leads") == 1
    assert _count(db_path, "campaigns") == 1
    assert _count(db_path, "outreach_queue") == 1


def test_legacy_queue_migration_preserves_rows_on_temp_copy(tmp_path):
    db_path = tmp_path / "legacy.db"
    _create_legacy_campaign_db(db_path)

    db_module.migrate_db(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, opener_text, template_text, full_message, status FROM outreach_queue ORDER BY id"
    ).fetchall()
    cols = {row[1] for row in conn.execute("PRAGMA table_info('outreach_queue')")}
    fks = {
        row[2] for row in conn.execute("PRAGMA foreign_key_list('outreach_queue')")
    }
    conn.close()

    assert [dict(row) for row in rows] == [
        {
            "id": 1,
            "opener_text": "Hi Alice",
            "template_text": "Template A",
            "full_message": "Full A",
            "status": "draft",
        },
        {
            "id": 2,
            "opener_text": "Hi Bob",
            "template_text": "Template B",
            "full_message": "Full B",
            "status": "approved",
        },
    ]
    assert {"skip_reason", "gate_checked_at", "sender_account_id"}.issubset(cols)
    assert "sender_accounts" in fks


def test_production_destructive_migration_requires_explicit_flag(tmp_path, monkeypatch):
    prod_copy = tmp_path / "leads.db"
    _create_legacy_campaign_db(prod_copy)

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(db_module, "DB_PATH", prod_copy)

    with pytest.raises(db_module.MigrationRequired):
        db_module.init_db(prod_copy)

    conn = sqlite3.connect(str(prod_copy))
    sender_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sender_accounts'"
    ).fetchone()
    conn.close()
    assert sender_table is None

    with pytest.raises(db_module.MigrationRequired):
        db_module.migrate_db(prod_copy)

    assert _count(prod_copy, "outreach_queue") == 2

    db_module.init_db(prod_copy, allow_destructive=True)

    conn = sqlite3.connect(str(prod_copy))
    cols = {row[1] for row in conn.execute("PRAGMA table_info('outreach_queue')")}
    conn.close()
    assert {"skip_reason", "gate_checked_at", "sender_account_id"}.issubset(cols)
    assert _count(prod_copy, "outreach_queue") == 2
