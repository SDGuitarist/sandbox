"""Tests for browser_sender module (unit tests, no actual browser)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from browser_sender import (
    detect_platform, check_for_restriction, AdaptiveDelay,
    acquire_lock, release_lock, LOCKFILE,
)


# ---------------------------------------------------------------------------
# detect_platform
# ---------------------------------------------------------------------------

def test_detect_facebook():
    assert detect_platform("https://www.facebook.com/john.doe") == "facebook"


def test_detect_instagram():
    assert detect_platform("https://www.instagram.com/johndoe") == "instagram"


def test_detect_unknown():
    assert detect_platform("https://www.linkedin.com/in/johndoe") is None


def test_detect_none_url():
    assert detect_platform("") is None


# ---------------------------------------------------------------------------
# check_for_restriction
# ---------------------------------------------------------------------------

def test_restriction_detects_login_url():
    page = MagicMock()
    page.url = "https://www.facebook.com/login?next=..."
    result = check_for_restriction(page, "facebook")
    assert result is not None
    assert "session_expired" in result


def test_restriction_detects_blocked_text():
    page = MagicMock()
    page.url = "https://www.facebook.com/messages"
    page.inner_text.return_value = "You're temporarily blocked from doing this."
    result = check_for_restriction(page, "facebook")
    assert result is not None
    assert "restriction" in result


def test_restriction_safe_page():
    page = MagicMock()
    page.url = "https://www.facebook.com/messages/t/12345"
    page.inner_text.return_value = "Hello! How are you?"
    result = check_for_restriction(page, "facebook")
    assert result is None


def test_restriction_ig_action_blocked():
    page = MagicMock()
    page.url = "https://www.instagram.com/direct/t/123"
    page.inner_text.return_value = "action blocked try again later"
    result = check_for_restriction(page, "instagram")
    assert result is not None


def test_restriction_handles_page_error():
    page = MagicMock()
    page.url = "https://www.facebook.com/messages"
    page.inner_text.side_effect = Exception("Page closed")
    result = check_for_restriction(page, "facebook")
    assert result is None  # Don't false-positive on errors


# ---------------------------------------------------------------------------
# AdaptiveDelay
# ---------------------------------------------------------------------------

def test_adaptive_delay_initial():
    d = AdaptiveDelay()
    delay = d.next_delay()
    assert 24 <= delay <= 36  # 30 * 0.8 to 30 * 1.2


def test_adaptive_delay_on_success_decreases():
    d = AdaptiveDelay()
    d.current_delay = 60
    for _ in range(15):
        d.on_success()
    assert d.current_delay < 60


def test_adaptive_delay_on_warning_increases():
    d = AdaptiveDelay()
    initial = d.current_delay
    d.on_warning()
    assert d.current_delay > initial
    assert d.sends_since_issue == 0


def test_adaptive_delay_max_cap():
    d = AdaptiveDelay()
    for _ in range(20):
        d.on_warning()
    assert d.current_delay <= d.max_delay


def test_batch_pause_every_15():
    d = AdaptiveDelay()
    assert d.should_batch_pause(0) is False
    assert d.should_batch_pause(15) is True
    assert d.should_batch_pause(16) is False
    assert d.should_batch_pause(30) is True


# ---------------------------------------------------------------------------
# Lockfile
# ---------------------------------------------------------------------------

def test_acquire_and_release_lock(tmp_path):
    """Test lockfile with custom path to avoid interfering with real lockfile."""
    import browser_sender
    original = browser_sender.LOCKFILE
    browser_sender.LOCKFILE = tmp_path / "test.lock"
    try:
        assert acquire_lock() is True
        assert browser_sender.LOCKFILE.exists()

        # Second acquire should fail (same PID is running)
        assert acquire_lock() is False

        release_lock()
        assert not browser_sender.LOCKFILE.exists()

        # After release, can acquire again
        assert acquire_lock() is True
        release_lock()
    finally:
        browser_sender.LOCKFILE = original


def test_stale_lock_overwritten(tmp_path):
    """Lock with dead PID should be overwritten."""
    import browser_sender
    original = browser_sender.LOCKFILE
    browser_sender.LOCKFILE = tmp_path / "test.lock"
    try:
        # Write a PID that doesn't exist
        browser_sender.LOCKFILE.write_text("999999999")
        assert acquire_lock() is True  # Should succeed (stale lock)
        release_lock()
    finally:
        browser_sender.LOCKFILE = original


# ---------------------------------------------------------------------------
# run_send integration (mocked Playwright)
# ---------------------------------------------------------------------------

def test_run_send_no_approved_messages(setup_db, tmp_path, capsys, monkeypatch):
    """run_send with no approved messages should exit cleanly."""
    import browser_sender
    from campaign import create_campaign

    monkeypatch.setattr(browser_sender, "LOCKFILE", tmp_path / "send.lock")
    monkeypatch.setattr(browser_sender, "STOPFILE", tmp_path / "send.stop")
    cid = create_campaign("Test", None, None, None, setup_db)
    browser_sender.run_send(cid, limit=5, db_path=setup_db)
    output = capsys.readouterr().out
    assert "No approved messages" in output


def test_run_send_no_risk_acknowledged_account(setup_db, insert_lead, tmp_path,
                                               capsys, monkeypatch):
    """run_send should refuse if no risk-acknowledged accounts."""
    import browser_sender
    from campaign import create_campaign, approve_message
    from account import add_account

    monkeypatch.setattr(browser_sender, "LOCKFILE", tmp_path / "send.lock")
    monkeypatch.setattr(browser_sender, "STOPFILE", tmp_path / "send.stop")

    # Create campaign with an approved message
    lid = insert_lead(setup_db, "Alice", profile_url="https://www.facebook.com/alice")
    cid = create_campaign("Test", None, None, None, setup_db)
    from db import get_db
    with get_db(setup_db) as conn:
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message, status) "
            "VALUES (?, ?, ?, 'approved')",
            (lid, cid, "Hello Alice"),
        )

    # Add account but don't confirm risk
    add_account("notrisk", db_path=setup_db)

    browser_sender.run_send(cid, limit=5, db_path=setup_db)
    output = capsys.readouterr().out
    assert "No risk-acknowledged accounts" in output
