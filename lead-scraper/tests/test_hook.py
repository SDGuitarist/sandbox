"""Tests for hook research enrichment step."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db, init_db
from enrich import (
    _get_leads_for_hook, _persist_hook, _research_single_hook,
    _build_hook_context, enrich_hook, EnrichmentResult,
)


def _setup_db(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    return db


def _insert_lead(db, name="Test", bio=None, segment=None, hook_text=None, **kw):
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO leads (name, bio, profile_url, source, segment, hook_text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, bio, f"https://example.com/{name.lower()}", "test", segment, hook_text),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_hook_requires_segment(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "NoSegment", bio="Writer", segment=None)
    _insert_lead(db, "HasSegment", bio="Writer", segment="writer")
    leads = _get_leads_for_hook(db)
    names = [l["name"] for l in leads]
    assert "NoSegment" not in names
    assert "HasSegment" in names


def test_hook_skips_already_researched(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "Already", bio="Writer", segment="writer", hook_text="Some hook")
    leads = _get_leads_for_hook(db)
    assert len(leads) == 0


def test_hook_stores_result_with_citation_url(tmp_path):
    db = _setup_db(tmp_path)
    lead_id = _insert_lead(db, "Alice", segment="writer")
    _persist_hook(lead_id, "Published a novel in March", "https://kpbs.org/article", 1, db)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT hook_text, hook_source_url, hook_quality FROM leads WHERE id = ?",
            (lead_id,)
        ).fetchone()
    assert row["hook_text"] == "Published a novel in March"
    assert row["hook_source_url"] == "https://kpbs.org/article"
    assert row["hook_quality"] == 1


def test_hook_stores_no_hook(tmp_path):
    db = _setup_db(tmp_path)
    lead_id = _insert_lead(db, "NoHook", segment="other")
    _persist_hook(lead_id, None, None, 0, db)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT hook_text, hook_source_url, hook_quality FROM leads WHERE id = ?",
            (lead_id,)
        ).fetchone()
    assert row["hook_text"] is None
    assert row["hook_source_url"] is None
    assert row["hook_quality"] == 0


def test_hook_handles_empty_citations():
    """When Sonar Pro returns no citations, source_url should be None."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "hook_text": "Gave a talk at a conference",
            "source_description": "Conference website",
            "tier": 3,
        })}}],
        "citations": [],  # empty citations
    }
    mock_session.post.return_value = mock_resp

    hook_text, source_url, tier = _research_single_hook(
        mock_session, "fake-key", "Alice", "Speaker in San Diego"
    )
    assert hook_text == "Gave a talk at a conference"
    assert source_url is None  # no citations -> None
    assert tier == 3


def test_hook_extracts_citation_url():
    """Source URL should come from citations[0], not from model output."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "hook_text": "Paris After Dark concert at the Conrad",
            "source_description": "KPBS event listing",
            "tier": 1,
        })}}],
        "citations": ["https://kpbs.org/events/paris-after-dark", "https://theconrad.org"],
    }
    mock_session.post.return_value = mock_resp

    hook_text, source_url, tier = _research_single_hook(
        mock_session, "fake-key", "Sacha Boutros", "Singer in San Diego"
    )
    assert source_url == "https://kpbs.org/events/paris-after-dark"  # citations[0]
    assert tier == 1


def test_hook_handles_cannot_find():
    """When model says it cannot find info, treat as no hook."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "hook_text": "Cannot find specific recent activity",
            "tier": 5,
        })}}],
        "citations": [],
    }
    mock_session.post.return_value = mock_resp

    hook_text, source_url, tier = _research_single_hook(
        mock_session, "fake-key", "Unknown Person", "San Diego"
    )
    assert hook_text is None
    assert tier == 0


def test_hook_handles_api_error():
    """Non-200 response should return no hook, not crash."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_session.post.return_value = mock_resp

    hook_text, source_url, tier = _research_single_hook(
        mock_session, "fake-key", "Alice", "Writer"
    )
    assert hook_text is None
    assert tier == 0


def test_hook_skips_if_no_api_key(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "Alice", segment="writer")
    with patch("config.get_perplexity_key", return_value=None):
        result = enrich_hook(db_path=db)
    assert result.leads_processed == 0


def test_build_hook_context():
    lead = {"name": "Alice", "bio": "Writer and novelist", "profile_bio": None,
            "activity": "Organized: Book Launch", "location": "San Diego, CA",
            "social_handles": None}
    ctx = _build_hook_context(lead)
    assert "Writer and novelist" in ctx
    assert "Book Launch" in ctx
    assert "San Diego" in ctx
