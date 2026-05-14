"""Tests for DB health checks, snapshots, and alerts."""

import sys
from argparse import Namespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import db
import run


def test_collect_db_health_reports_counts(setup_db):
    health = db.collect_db_health(setup_db)

    assert health["exists"] is True
    assert health["integrity_ok"] is True
    assert health["lead_count"] == 0
    assert health["campaign_count"] == 0
    assert health["queue_count"] == 0


def test_run_db_health_check_refreshes_snapshot(setup_db):
    health, warnings = db.run_db_health_check(setup_db, refresh_snapshot=True)
    snapshot_path = db.get_db_health_snapshot_path(setup_db)

    assert warnings == []
    assert snapshot_path.exists()
    assert db._load_db_health_snapshot(setup_db)["lead_count"] == health["lead_count"]


def test_run_db_health_check_raises_on_lead_collapse(setup_db):
    with db.get_db(setup_db) as conn:
        rows = [
            (f"Lead {i}", f"https://example.com/{i}", "test")
            for i in range(120)
        ]
        conn.executemany(
            "INSERT INTO leads (name, profile_url, source) VALUES (?, ?, ?)",
            rows,
        )

    db.run_db_health_check(setup_db, refresh_snapshot=True)

    with db.get_db(setup_db) as conn:
        conn.execute("DELETE FROM leads")

    with pytest.raises(db.DatabaseHealthError):
        db.run_db_health_check(setup_db)


def test_cmd_db_check_prints_summary(monkeypatch, capsys):
    monkeypatch.setattr(
        run,
        "run_db_health_check",
        lambda **kwargs: (
            {
                "exists": True,
                "file_size": 1024,
                "integrity_message": "ok",
                "lead_count": 12,
                "campaign_count": 3,
                "queue_count": 8,
            },
            ["Lead count dropped from 20 to 12 (8 fewer, 40% drop)."],
        ),
    )

    args = Namespace(refresh_snapshot=True, no_notify=True)
    run.cmd_db_check(args)
    output = capsys.readouterr().out

    assert "Database health:" in output
    assert "Leads:         12" in output
    assert "Warnings:" in output
    assert "Baseline snapshot updated." in output


def test_run_db_health_check_sends_email_on_warning(monkeypatch, setup_db):
    with db.get_db(setup_db) as conn:
        rows = [
            (f"Lead {i}", f"https://example.com/{i}", "test")
            for i in range(120)
        ]
        conn.executemany(
            "INSERT INTO leads (name, profile_url, source) VALUES (?, ?, ?)",
            rows,
        )

    db.run_db_health_check(setup_db, refresh_snapshot=True)

    with db.get_db(setup_db) as conn:
        conn.execute("DELETE FROM leads WHERE id <= 30")

    emails = []
    monkeypatch.setattr(db, "_send_macos_notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(db, "_send_email_notification", lambda subject, message: emails.append((subject, message)))

    health, warnings = db.run_db_health_check(setup_db, notify=True)

    assert warnings
    assert emails
    assert emails[0][0] == "Lead Scraper DB Warning"
    assert "Lead count dropped" in emails[0][1]
    assert health["lead_count"] == 90


def test_run_db_health_check_sends_email_on_hard_failure(monkeypatch):
    emails = []
    monkeypatch.setattr(db, "_send_macos_notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(db, "_send_email_notification", lambda subject, message: emails.append((subject, message)))

    with pytest.raises(db.DatabaseHealthError):
        db.run_db_health_check(Path("/tmp/definitely-missing-leads.db"), notify=True)

    assert emails
    assert emails[0][0] == "Lead Scraper DB Alert"
    assert "missing" in emails[0][1]
