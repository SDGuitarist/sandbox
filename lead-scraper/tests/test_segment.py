"""Tests for segment classification enrichment step."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db
from enrich import (
    _get_leads_for_segment, _persist_segment, _classify_single_lead,
    enrich_segment, EnrichmentResult,
)


def test_segment_selects_null_segment_only(setup_db, insert_lead):
    insert_lead(setup_db, "Unclassified", bio="Writer and author")
    insert_lead(setup_db, "Classified", bio="Realtor", segment="real_estate")
    leads = _get_leads_for_segment(setup_db)
    names = [l["name"] for l in leads]
    assert "Unclassified" in names
    assert "Classified" not in names


def test_segment_stores_result(setup_db, insert_lead):
    lead_id = insert_lead(setup_db, "Alice", bio="Yoga teacher")
    _persist_segment(lead_id, "wellness", 0.9, setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT segment, segment_confidence FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()
    assert row["segment"] == "wellness"
    assert row["segment_confidence"] == 0.9


def test_segment_prefilters_empty_bios():
    """Bio under 3 chars should return 'other' without API call."""
    mock_client = MagicMock()
    segment, confidence = _classify_single_lead(mock_client, "Alice", "", "")
    assert segment == "other"
    assert confidence == 0.1
    # Client should NOT have been called
    mock_client.messages.parse.assert_not_called()


def test_segment_prefilters_short_bios():
    mock_client = MagicMock()
    segment, confidence = _classify_single_lead(mock_client, "Bob", "Hi", "")
    assert segment == "other"
    assert confidence == 0.1
    mock_client.messages.parse.assert_not_called()


def test_segment_handles_api_error():
    """API error should return 'other' with 0.0 confidence, not crash."""
    mock_client = MagicMock()
    mock_client.messages.parse.side_effect = Exception("API timeout")
    segment, confidence = _classify_single_lead(
        mock_client, "Alice", "Professional writer and novelist", ""
    )
    assert segment == "other"
    assert confidence == 0.0


def test_segment_handles_refusal():
    """Model refusal should return 'other' with 0.0 confidence."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.stop_reason = "refusal"
    mock_client.messages.parse.return_value = mock_response
    segment, confidence = _classify_single_lead(
        mock_client, "Alice", "Some bio text here", ""
    )
    assert segment == "other"
    assert confidence == 0.0


def test_segment_successful_classification():
    """Successful classification returns parsed segment and confidence."""
    mock_client = MagicMock()
    mock_parsed = MagicMock()
    mock_parsed.segment = "writer"
    mock_parsed.confidence = 0.92
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.parsed_output = mock_parsed
    mock_client.messages.parse.return_value = mock_response

    segment, confidence = _classify_single_lead(
        mock_client, "Alice", "Published author of three novels", ""
    )
    assert segment == "writer"
    assert confidence == 0.92


def test_enrich_segment_skips_without_api_key(setup_db, insert_lead):
    """Should skip gracefully when ANTHROPIC_API_KEY is not set."""
    insert_lead(setup_db, "Alice", bio="Writer")
    with patch.dict("os.environ", {}, clear=False):
        # Remove the key if present
        import os
        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result = enrich_segment(db_path=setup_db)
            assert result.leads_processed == 0
        finally:
            if old:
                os.environ["ANTHROPIC_API_KEY"] = old
