"""Tests for source type dispatch and _NON_OVERRIDABLE_FIELDS."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import BASE_SOURCES, _merge_sources, _NON_OVERRIDABLE_FIELDS


class TestSourceTypes:
    """Verify all sources have a type field."""

    def test_all_sources_have_type(self) -> None:
        for name, cfg in BASE_SOURCES.items():
            assert "type" in cfg, f"Source '{name}' missing 'type' field"

    def test_existing_sources_are_apify(self) -> None:
        for name in ("eventbrite", "facebook", "instagram", "linkedin", "meetup"):
            assert BASE_SOURCES[name]["type"] == "apify"

    def test_venue_csv_is_csv_type(self) -> None:
        assert BASE_SOURCES["venue_csv"]["type"] == "csv"
        assert BASE_SOURCES["venue_csv"]["source_name"] == "venue_scraper"

    def test_google_is_serpapi_type(self) -> None:
        assert BASE_SOURCES["google"]["type"] == "serpapi"
        assert BASE_SOURCES["google"]["enabled"] is False


class TestNonOverridableFields:
    """Verify _NON_OVERRIDABLE_FIELDS protects type from overrides."""

    def test_type_in_non_overridable(self) -> None:
        assert "type" in _NON_OVERRIDABLE_FIELDS

    def test_type_not_overridable(self) -> None:
        """sources.overrides.json with type change must NOT change dispatch routing."""
        overrides = {"eventbrite": {"type": "csv"}}
        merged = _merge_sources(BASE_SOURCES, overrides)
        assert merged["eventbrite"]["type"] == "apify"

    def test_list_overrides_still_work(self) -> None:
        """_add overrides must still work after _NON_OVERRIDABLE_FIELDS is added."""
        overrides = {"eventbrite": {"keywords_add": ["new keyword for testing"]}}
        merged = _merge_sources(BASE_SOURCES, overrides)
        assert "new keyword for testing" in merged["eventbrite"]["keywords"]

    def test_scalar_overrides_still_work(self) -> None:
        """Non-protected scalar overrides should still apply."""
        overrides = {"eventbrite": {"max_pages": 5}}
        merged = _merge_sources(BASE_SOURCES, overrides)
        assert merged["eventbrite"]["max_pages"] == 5
