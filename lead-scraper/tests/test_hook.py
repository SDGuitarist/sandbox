"""Tests for hook research enrichment step."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db
from enrich import (
    _get_leads_for_hook, _persist_hook, _research_single_hook,
    _build_hook_context, enrich_hook, EnrichmentResult,
)


def test_hook_requires_segment(setup_db, insert_lead):
    insert_lead(setup_db, "NoSegment", bio="Writer", segment=None)
    insert_lead(setup_db, "HasSegment", bio="Writer", segment="writer")
    leads = _get_leads_for_hook(setup_db)
    names = [l["name"] for l in leads]
    assert "NoSegment" not in names
    assert "HasSegment" in names


def test_hook_skips_already_researched(setup_db, insert_lead):
    insert_lead(setup_db, "Already", bio="Writer", segment="writer", hook_text="Some hook")
    leads = _get_leads_for_hook(setup_db)
    assert len(leads) == 0


def test_hook_stores_result_with_citation_url(setup_db, insert_lead):
    lead_id = insert_lead(setup_db, "Alice", segment="writer")
    _persist_hook(lead_id, "Published a novel in March", "https://kpbs.org/article", 1, setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT hook_text, hook_source_url, hook_quality FROM leads WHERE id = ?",
            (lead_id,)
        ).fetchone()
    assert row["hook_text"] == "Published a novel in March"
    assert row["hook_source_url"] == "https://kpbs.org/article"
    assert row["hook_quality"] == 1


def test_hook_stores_no_hook(setup_db, insert_lead):
    lead_id = insert_lead(setup_db, "NoHook", segment="other")
    _persist_hook(lead_id, None, None, 0, setup_db)
    with get_db(setup_db) as conn:
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


def test_hook_skips_if_no_api_key(setup_db, insert_lead):
    insert_lead(setup_db, "Alice", segment="writer")
    with patch("config.get_perplexity_key", return_value=None):
        result = enrich_hook(db_path=setup_db)
    assert result.leads_processed == 0


def test_build_hook_context():
    lead = {"name": "Alice", "bio": "Writer and novelist", "profile_bio": None,
            "activity": "Organized: Book Launch", "location": "San Diego, CA",
            "social_handles": None}
    ctx = _build_hook_context(lead)
    assert "Writer and novelist" in ctx
    assert "Book Launch" in ctx
    assert "San Diego" in ctx


@patch("enrich.time.sleep")
def test_hook_research_retries_429_then_succeeds(mock_sleep):
    """429 on first attempt -> retry -> 200 on second attempt. Lead is processed."""
    mock_session = MagicMock()
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.headers = {"retry-after": "2"}

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "hook_text": "Keynote speaker at AI Summit",
            "source_description": "Event page",
            "tier": 1,
        })}}],
        "citations": ["https://aisummit.com/speakers"],
    }

    mock_session.post.side_effect = [mock_429, mock_200]

    hook_text, source_url, tier = _research_single_hook(
        mock_session, "fake-key", "Alice", "Speaker in San Diego"
    )
    assert hook_text == "Keynote speaker at AI Summit"
    assert tier == 1
    assert mock_session.post.call_count == 2


@patch("enrich.time.sleep")
def test_hook_research_429_exhausted_skips_persist(mock_sleep):
    """429 three times -> tier=-1 returned. hook_quality must NOT be persisted."""
    mock_session = MagicMock()
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.headers = {"retry-after": "1"}

    mock_session.post.return_value = mock_429

    hook_text, source_url, tier = _research_single_hook(
        mock_session, "fake-key", "Alice", "Writer"
    )
    assert tier == -1  # Transient failure signal
    assert hook_text is None
    assert mock_session.post.call_count == 3  # Tried 3 times


@patch("enrich.requests.Session")
@patch("enrich.time.sleep")
def test_enrich_hook_429_leaves_hook_quality_null(mock_sleep, mock_session_cls,
                                                   setup_db, insert_lead):
    """Full enrich_hook(): 3x429 must leave hook_quality as NULL in the database."""
    lead_id = insert_lead(setup_db, "Alice", segment="writer",
                          segment_confidence=0.9)

    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.headers = {"retry-after": "1"}

    mock_session = MagicMock()
    mock_session.post.return_value = mock_429
    mock_session_cls.return_value = mock_session

    with patch("config.get_perplexity_key", return_value="fake-key"):
        enrich_hook(db_path=setup_db)

    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT hook_quality, hook_text FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()
    assert row["hook_quality"] is None  # NOT persisted as 0
    assert row["hook_text"] is None
