"""Tests for the safe workflow CLI orchestration."""

import sys
from argparse import Namespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import run
from db import (
    MigrationSafetyError,
    acquire_db_job_lock,
    release_db_job_lock,
)


def test_db_job_lock_roundtrip(tmp_path):
    lock_path = tmp_path / "db.lock"

    assert acquire_db_job_lock(lock_path) is True
    assert acquire_db_job_lock(lock_path) is False

    release_db_job_lock(lock_path)

    assert acquire_db_job_lock(lock_path) is True
    release_db_job_lock(lock_path)


def test_workflow_daily_runs_safe_sequence(monkeypatch):
    calls = []

    monkeypatch.setattr(run, "cmd_scrape", lambda args: calls.append(("scrape", args.location)))
    monkeypatch.setattr(run, "_print_db_status", lambda *args, **kwargs: calls.append(("status", None)))

    def fake_assign(campaign_id, min_hook_quality):
        calls.append(("assign", campaign_id, min_hook_quality))

    def fake_generate(campaign_id, limit):
        calls.append(("generate", campaign_id, limit))

    def fake_gate(campaign_id, limit, force):
        calls.append(("gate", campaign_id, limit, force))

    monkeypatch.setattr("campaign.assign_leads", fake_assign)
    monkeypatch.setattr("campaign.generate_messages", fake_generate)
    monkeypatch.setattr("quality_gate.run_gate", fake_gate)

    args = Namespace(
        action="daily",
        location="San Diego, CA",
        campaign_id=7,
        min_hook_quality=2,
        generate_limit=25,
        gate_limit=10,
        skip_gate=False,
        force_gate=True,
    )

    run.cmd_workflow(args)

    assert calls == [
        ("scrape", "San Diego, CA"),
        ("assign", 7, 2),
        ("generate", 7, 25),
        ("gate", 7, 10, True),
        ("status", None),
    ]


def test_workflow_outreach_prep_can_skip_gate(monkeypatch):
    calls = []

    monkeypatch.setattr(run, "_print_db_status", lambda *args, **kwargs: calls.append(("status", None)))
    monkeypatch.setattr(run, "cmd_enrich", lambda args: calls.append(("enrich", args.step)))

    monkeypatch.setattr("campaign.assign_leads", lambda cid, min_hook_quality: calls.append(("assign", cid, min_hook_quality)))
    monkeypatch.setattr("campaign.generate_messages", lambda cid, limit: calls.append(("generate", cid, limit)))

    args = Namespace(
        action="outreach-prep",
        campaign_id=11,
        min_hook_quality=3,
        generate_limit=40,
        gate_limit=0,
        skip_gate=True,
        force_gate=False,
        run_enrich=True,
        step="all",
        limit=50,
        refresh=False,
        days=30,
    )

    run.cmd_workflow(args)

    assert calls == [
        ("enrich", "all"),
        ("assign", 11, 3),
        ("generate", 11, 40),
        ("status", None),
    ]


def test_workflow_status_prints_summary(setup_db, capsys):
    run._print_db_status(setup_db)
    output = capsys.readouterr().out
    assert "Database status:" in output
    assert "Leads:" in output


def test_main_refuses_when_db_lock_is_held(tmp_path, monkeypatch):
    lock_path = tmp_path / "db.lock"
    acquire_db_job_lock(lock_path)
    monkeypatch.setattr(run, "DB_JOB_LOCKFILE", lock_path)

    original_context = run.db_job_lock

    def patched_db_job_lock(lock_override=run.DB_JOB_LOCKFILE):
        return original_context(lock_path)

    monkeypatch.setattr(run, "db_job_lock", patched_db_job_lock)
    monkeypatch.setattr(run, "init_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(run, "create_backup", lambda *args, **kwargs: None)
    monkeypatch.setattr(run, "cmd_scrape", lambda args: None)

    monkeypatch.setattr(sys, "argv", ["run.py", "workflow", "scrape-only", "--location", "San Diego, CA"])

    with pytest.raises(MigrationSafetyError):
        with run.db_job_lock():
            pass

    with pytest.raises(SystemExit) as exc:
        run.main()

    release_db_job_lock(lock_path)
    assert exc.value.code == 2
