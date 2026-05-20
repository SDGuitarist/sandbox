"""Tests for Phase 4: LLM extraction, domain mismatch, screen_leads preservation, clear-mismatch.

All tests are mock-based -- no real API calls.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import init_db, get_db
from enrich import (
    _check_domain_mismatch,
    _persist_lead_update,
    _strip_html_to_text,
    screen_leads,
)
from models import clear_domain_mismatch, query_held_leads, unhold_lead


def _setup_db(db_path: Path, leads: list[dict] | None = None) -> None:
    """Create test DB with optional lead data."""
    init_db(db_path, allow_create_production=False)
    if leads:
        with get_db(db_path) as conn:
            for lead in leads:
                conn.execute(
                    """INSERT INTO leads (name, profile_url, source, website, email,
                        is_sendable, sendable_reason)
                    VALUES (:name, :profile_url, :source, :website, :email,
                        :is_sendable, :sendable_reason)""",
                    {
                        "name": lead.get("name", "Test"),
                        "profile_url": lead.get("profile_url", "https://test.com"),
                        "source": lead.get("source", "eventbrite"),
                        "website": lead.get("website"),
                        "email": lead.get("email"),
                        "is_sendable": lead.get("is_sendable"),
                        "sendable_reason": lead.get("sendable_reason"),
                    },
                )


class TestStripHtmlToText:

    def test_strips_script_tags(self) -> None:
        html = "<p>Hello</p><script>var x=1;</script><p>World</p>"
        text = _strip_html_to_text(html)
        assert "Hello" in text
        assert "World" in text
        assert "var" not in text

    def test_strips_style_tags(self) -> None:
        html = "<style>body{color:red}</style><p>Content</p>"
        text = _strip_html_to_text(html)
        assert "Content" in text
        assert "color" not in text

    def test_empty_html_returns_empty(self) -> None:
        assert _strip_html_to_text("") == ""


class TestCheckDomainMismatch:

    def test_matching_domains(self) -> None:
        assert _check_domain_mismatch("user@example.com", "https://example.com") is False

    def test_mismatching_domains(self) -> None:
        assert _check_domain_mismatch("user@other.com", "https://example.com") is True

    def test_subdomain_match(self) -> None:
        assert _check_domain_mismatch("user@mail.example.com", "https://example.com") is False

    def test_none_email(self) -> None:
        assert _check_domain_mismatch(None, "https://example.com") is False

    def test_no_at_sign(self) -> None:
        assert _check_domain_mismatch("not-an-email", "https://example.com") is False

    def test_gmail_on_personal_site(self) -> None:
        assert _check_domain_mismatch("user@gmail.com", "https://personalsite.com") is True


class TestPersistLeadUpdate:

    def test_coalesce_preserves_existing_email(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path, [{"name": "Test", "email": "existing@test.com", "website": "https://test.com"}])

        _persist_lead_update(1, {"email": "new@test.com"}, db_path)

        with get_db(db_path) as conn:
            row = conn.execute("SELECT email FROM leads WHERE id = 1").fetchone()
        assert row["email"] == "existing@test.com"

    def test_fills_null_email(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path, [{"name": "Test", "email": None, "website": "https://test.com"}])

        _persist_lead_update(1, {"email": "found@test.com"}, db_path)

        with get_db(db_path) as conn:
            row = conn.execute("SELECT email FROM leads WHERE id = 1").fetchone()
        assert row["email"] == "found@test.com"

    def test_force_enriched_at_overwrites(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path, [{"name": "Test", "website": "https://test.com"}])

        # First enrichment
        _persist_lead_update(1, {}, db_path)
        with get_db(db_path) as conn:
            first = conn.execute("SELECT enriched_at FROM leads WHERE id = 1").fetchone()["enriched_at"]

        # Second enrichment with force
        import time
        time.sleep(0.01)
        _persist_lead_update(1, {}, db_path, force_enriched_at=True)
        with get_db(db_path) as conn:
            second = conn.execute("SELECT enriched_at FROM leads WHERE id = 1").fetchone()["enriched_at"]

        assert second >= first  # Updated, not COALESCE'd

    def test_default_coalesce_enriched_at(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path, [{"name": "Test", "website": "https://test.com"}])

        _persist_lead_update(1, {}, db_path)
        with get_db(db_path) as conn:
            first = conn.execute("SELECT enriched_at FROM leads WHERE id = 1").fetchone()["enriched_at"]

        # Second without force -- should keep first
        _persist_lead_update(1, {}, db_path, force_enriched_at=False)
        with get_db(db_path) as conn:
            second = conn.execute("SELECT enriched_at FROM leads WHERE id = 1").fetchone()["enriched_at"]

        assert second == first


class TestScreenLeadsPreservesMismatch:

    def test_preserves_domain_mismatch_hold(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path, [{
            "name": "Mismatch Lead",
            "profile_url": "https://facebook.com/mismatch.person",
            "website": "https://test.com",
            "is_sendable": 0,
            "sendable_reason": "email_domain_mismatch",
        }])

        screen_leads(db_path=db_path)

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT is_sendable, sendable_reason FROM leads WHERE id = 1"
            ).fetchone()
        # Mismatch hold preserved even though lead passes screening
        assert row["is_sendable"] == 0
        assert row["sendable_reason"] == "email_domain_mismatch"

    def test_normal_lead_passes_screening(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path, [{
            "name": "Normal Lead",
            "profile_url": "https://facebook.com/person",
            "website": "https://test.com",
            "is_sendable": None,
            "sendable_reason": None,
        }])

        screen_leads(db_path=db_path)

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT is_sendable, sendable_reason FROM leads WHERE id = 1"
            ).fetchone()
        assert row["is_sendable"] == 1
        assert row["sendable_reason"] is None


class TestClearDomainMismatch:

    def test_clears_mismatch_hold(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path, [{
            "name": "Mismatch Lead",
            "is_sendable": 0,
            "sendable_reason": "email_domain_mismatch",
        }])

        result = clear_domain_mismatch(1, db_path)
        assert result is True

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT is_sendable, sendable_reason FROM leads WHERE id = 1"
            ).fetchone()
        assert row["is_sendable"] == 1
        assert row["sendable_reason"] is None

    def test_refuses_to_clear_org_name_hold(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path, [{
            "name": "Org Lead",
            "is_sendable": 0,
            "sendable_reason": "org_name",
        }])

        result = clear_domain_mismatch(1, db_path)
        assert result is False

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT is_sendable, sendable_reason FROM leads WHERE id = 1"
            ).fetchone()
        assert row["is_sendable"] == 0
        assert row["sendable_reason"] == "org_name"


class TestQueryHeldLeadsMismatch:

    def test_mismatch_appears_in_held_list(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path, [{
            "name": "Mismatch Lead",
            "is_sendable": 0,
            "sendable_reason": "email_domain_mismatch",
        }])

        held = query_held_leads(db_path)
        mismatch_holds = [h for h in held if h["hold_reason"] == "email_domain_mismatch"]
        assert len(mismatch_holds) == 1
        assert mismatch_holds[0]["name"] == "Mismatch Lead"

    def test_mismatch_visible_even_with_manual_approved(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path, [{
            "name": "Approved Mismatch",
            "is_sendable": 0,
            "sendable_reason": "email_domain_mismatch",
        }])

        # Set manual_approved=1 (operator ran 'leads unhold')
        unhold_lead(1, db_path)

        held = query_held_leads(db_path)
        mismatch_holds = [h for h in held if h["hold_reason"] == "email_domain_mismatch"]
        # Still visible -- mismatch UNION has no manual_approved filter
        assert len(mismatch_holds) == 1

    def test_unhold_does_not_clear_mismatch(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path, [{
            "name": "Mismatch Lead",
            "is_sendable": 0,
            "sendable_reason": "email_domain_mismatch",
        }])

        unhold_lead(1, db_path)

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT is_sendable, sendable_reason, manual_approved FROM leads WHERE id = 1"
            ).fetchone()
        # manual_approved set, but is_sendable still 0
        assert row["manual_approved"] == 1
        assert row["is_sendable"] == 0
        assert row["sendable_reason"] == "email_domain_mismatch"
