"""Tests for sender account CRUD and state machine."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db
from account import (
    add_account, list_accounts, get_active_account, increment_sends,
    mark_restricted, set_cooldown, check_cooldown_expired,
    disable_account, enable_account,
)


def _add_test_account(db, name="sender1", platform="both", daily_cap=30):
    """Helper: add account and return its ID."""
    add_account(name, platform=platform, daily_cap=daily_cap, db_path=db)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT id FROM sender_accounts WHERE name = ?", (name,)
        ).fetchone()
    return row["id"]


def test_add_account(setup_db):
    add_account("test-acct", platform="facebook", daily_cap=20, db_path=setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT * FROM sender_accounts WHERE name = 'test-acct'"
        ).fetchone()
    assert row is not None
    assert row["platform"] == "facebook"
    assert row["daily_cap"] == 20
    assert row["status"] == "active"
    assert row["risk_acknowledged"] == 0
    assert "test-acct" in row["profile_dir"]


def test_add_duplicate_name_fails(setup_db):
    add_account("dupe", db_path=setup_db)
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        add_account("dupe", db_path=setup_db)


def test_list_accounts_empty(setup_db, capsys):
    list_accounts(db_path=setup_db)
    output = capsys.readouterr().out
    assert "No sender accounts" in output


def test_list_accounts_shows_data(setup_db, capsys):
    _add_test_account(setup_db, "acct1", "instagram")
    list_accounts(db_path=setup_db)
    output = capsys.readouterr().out
    assert "acct1" in output
    assert "instagram" in output


def test_get_active_account_none_when_empty(setup_db):
    result = get_active_account("facebook", db_path=setup_db)
    assert result is None


def test_get_active_account_requires_risk_acknowledged(setup_db):
    _add_test_account(setup_db, "unacked")
    # Not risk-acknowledged, should not be returned
    result = get_active_account("both", db_path=setup_db)
    assert result is None


def test_get_active_account_returns_acknowledged(setup_db):
    aid = _add_test_account(setup_db, "acked")
    with get_db(setup_db) as conn:
        conn.execute(
            "UPDATE sender_accounts SET risk_acknowledged = 1 WHERE id = ?", (aid,)
        )
    result = get_active_account("both", db_path=setup_db)
    assert result is not None
    assert result["name"] == "acked"


def test_get_active_account_platform_filter(setup_db):
    aid = _add_test_account(setup_db, "fb-only", platform="facebook")
    with get_db(setup_db) as conn:
        conn.execute(
            "UPDATE sender_accounts SET risk_acknowledged = 1 WHERE id = ?", (aid,)
        )
    # Should match facebook
    assert get_active_account("facebook", db_path=setup_db) is not None
    # Should NOT match instagram (platform is 'facebook', not 'both')
    assert get_active_account("instagram", db_path=setup_db) is None


def test_get_active_account_respects_daily_cap(setup_db):
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    aid = _add_test_account(setup_db, "capped", daily_cap=2)
    with get_db(setup_db) as conn:
        conn.execute(
            "UPDATE sender_accounts SET risk_acknowledged = 1, sends_today = 2, "
            "last_reset_date = ? WHERE id = ?", (today, aid)
        )
    result = get_active_account("both", db_path=setup_db)
    assert result is None  # At cap


def test_increment_sends(setup_db):
    aid = _add_test_account(setup_db)
    with get_db(setup_db) as conn:
        conn.execute(
            "UPDATE sender_accounts SET risk_acknowledged = 1 WHERE id = ?", (aid,)
        )
    increment_sends(aid, db_path=setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT sends_today, last_send_at FROM sender_accounts WHERE id = ?", (aid,)
        ).fetchone()
    assert row["sends_today"] == 1
    assert row["last_send_at"] is not None


def test_increment_sends_fails_when_not_active(setup_db):
    aid = _add_test_account(setup_db)
    with get_db(setup_db) as conn:
        conn.execute(
            "UPDATE sender_accounts SET status = 'disabled' WHERE id = ?", (aid,)
        )
    with pytest.raises(AssertionError, match="not found or not active"):
        increment_sends(aid, db_path=setup_db)


def test_mark_restricted(setup_db):
    aid = _add_test_account(setup_db)
    mark_restricted(aid, db_path=setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, restricted_at FROM sender_accounts WHERE id = ?", (aid,)
        ).fetchone()
    assert row["status"] == "restricted"
    assert row["restricted_at"] is not None


def test_mark_restricted_fails_when_not_active(setup_db):
    aid = _add_test_account(setup_db)
    with get_db(setup_db) as conn:
        conn.execute(
            "UPDATE sender_accounts SET status = 'disabled' WHERE id = ?", (aid,)
        )
    with pytest.raises(AssertionError, match="not found or not active"):
        mark_restricted(aid, db_path=setup_db)


def test_set_cooldown(setup_db):
    aid = _add_test_account(setup_db)
    mark_restricted(aid, db_path=setup_db)
    set_cooldown(aid, hours=48, db_path=setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, cooldown_until FROM sender_accounts WHERE id = ?", (aid,)
        ).fetchone()
    assert row["status"] == "cooldown"
    assert row["cooldown_until"] is not None


def test_set_cooldown_fails_when_not_restricted(setup_db):
    aid = _add_test_account(setup_db)  # status = active
    with pytest.raises(AssertionError, match="not found or not restricted"):
        set_cooldown(aid, hours=24, db_path=setup_db)


def test_check_cooldown_expired(setup_db):
    aid = _add_test_account(setup_db)
    mark_restricted(aid, db_path=setup_db)
    # Set cooldown to 1 hour ago (already expired)
    past = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db(setup_db) as conn:
        conn.execute(
            "UPDATE sender_accounts SET status = 'cooldown', cooldown_until = ? "
            "WHERE id = ?", (past, aid)
        )
    check_cooldown_expired(db_path=setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, sends_today FROM sender_accounts WHERE id = ?", (aid,)
        ).fetchone()
    assert row["status"] == "active"
    assert row["sends_today"] == 0


def test_check_cooldown_not_expired(setup_db):
    aid = _add_test_account(setup_db)
    mark_restricted(aid, db_path=setup_db)
    # Set cooldown to 1 hour in the future
    future = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db(setup_db) as conn:
        conn.execute(
            "UPDATE sender_accounts SET status = 'cooldown', cooldown_until = ? "
            "WHERE id = ?", (future, aid)
        )
    check_cooldown_expired(db_path=setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status FROM sender_accounts WHERE id = ?", (aid,)
        ).fetchone()
    assert row["status"] == "cooldown"  # Still in cooldown


def test_disable_account(setup_db):
    aid = _add_test_account(setup_db)
    disable_account(aid, db_path=setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status FROM sender_accounts WHERE id = ?", (aid,)
        ).fetchone()
    assert row["status"] == "disabled"


def test_disable_already_disabled_fails(setup_db):
    aid = _add_test_account(setup_db)
    disable_account(aid, db_path=setup_db)
    with pytest.raises(AssertionError, match="already disabled"):
        disable_account(aid, db_path=setup_db)


def test_enable_account(setup_db):
    aid = _add_test_account(setup_db)
    disable_account(aid, db_path=setup_db)
    enable_account(aid, db_path=setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, sends_today FROM sender_accounts WHERE id = ?", (aid,)
        ).fetchone()
    assert row["status"] == "active"
    assert row["sends_today"] == 0


def test_enable_fails_when_not_disabled(setup_db):
    aid = _add_test_account(setup_db)  # status = active
    with pytest.raises(AssertionError, match="not found or not disabled"):
        enable_account(aid, db_path=setup_db)


def test_get_active_picks_lowest_sends(setup_db):
    """Round-robin: pick account with lowest sends_today."""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    aid1 = _add_test_account(setup_db, "busy")
    aid2 = _add_test_account(setup_db, "fresh")
    with get_db(setup_db) as conn:
        conn.execute(
            "UPDATE sender_accounts SET risk_acknowledged = 1, sends_today = 10, "
            "last_reset_date = ? WHERE id = ?", (today, aid1)
        )
        conn.execute(
            "UPDATE sender_accounts SET risk_acknowledged = 1, sends_today = 2, "
            "last_reset_date = ? WHERE id = ?", (today, aid2)
        )
    result = get_active_account("both", db_path=setup_db)
    assert result["name"] == "fresh"  # Lower sends_today
