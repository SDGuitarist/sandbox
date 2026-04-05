"""Verify-first: rate limit window exhaustion and reset."""
import os
from datetime import datetime, timedelta, timezone

import pytest

from chat.db import check_rate_limit, init_db


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    monkeypatch.setattr("chat.db.SCHEMA_PATH",
                        __import__("pathlib").Path(__file__).parent.parent / "chat" / "schema.sql")
    init_db(path=path)
    return path


def test_rate_limit_first_request_allowed(db):
    assert check_rate_limit("alice", max_count=3, db_path=db) is True


def test_rate_limit_window_exhaustion(db):
    """First N requests succeed, N+1 returns False."""
    for i in range(20):
        result = check_rate_limit("bob", max_count=20, db_path=db)
        assert result is True, f"Request {i+1} should be allowed"
    assert check_rate_limit("bob", max_count=20, db_path=db) is False


def test_rate_limit_independent_per_user(db):
    """Rate limit for alice does not affect bob."""
    for _ in range(20):
        check_rate_limit("alice", max_count=20, db_path=db)
    # alice is exhausted
    assert check_rate_limit("alice", max_count=20, db_path=db) is False
    # bob is unaffected
    assert check_rate_limit("bob", max_count=20, db_path=db) is True


def test_rate_limit_window_reset(db):
    """After window expires, counter resets and requests are allowed again."""
    import sqlite3

    # Exhaust the window
    for _ in range(20):
        check_rate_limit("carol", max_count=20, window_seconds=60, db_path=db)
    assert check_rate_limit("carol", max_count=20, window_seconds=60, db_path=db) is False

    # Backdate window_start to simulate window expiry
    conn = sqlite3.connect(db)
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=61)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE rate_limits SET window_start = ? WHERE user_id = ?", (old_time, "carol"))
    conn.commit()
    conn.close()

    # Now the window should reset
    assert check_rate_limit("carol", max_count=20, window_seconds=60, db_path=db) is True


def test_rate_limit_partial_window_not_reset(db):
    """Window has not expired yet — counter continues from where it left off."""
    for _ in range(10):
        check_rate_limit("dave", max_count=20, window_seconds=60, db_path=db)
    # 10 used, 10 remain — should still be allowed
    assert check_rate_limit("dave", max_count=20, window_seconds=60, db_path=db) is True
