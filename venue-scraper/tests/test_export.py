"""Tests for export.py -- CSV export and sanitization."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from export import export_outreach_csv, sanitize_cell


class TestSanitizeCell:
    """Test CSV formula injection prevention."""

    def test_normal_text_unchanged(self) -> None:
        assert sanitize_cell("Studio West") == "Studio West"

    def test_equals_sign_prefixed(self) -> None:
        assert sanitize_cell("=1+1") == "'=1+1"

    def test_minus_sign_prefixed(self) -> None:
        assert sanitize_cell("-cmd") == "'-cmd"

    def test_plus_sign_prefixed(self) -> None:
        assert sanitize_cell("+cmd") == "'+cmd"

    def test_at_sign_prefixed(self) -> None:
        assert sanitize_cell("@SUM(A1)") == "'@SUM(A1)"

    def test_pipe_sign_prefixed(self) -> None:
        assert sanitize_cell("|cmd") == "'|cmd"

    def test_none_returns_empty(self) -> None:
        assert sanitize_cell(None) == ""

    def test_empty_string_returns_empty(self) -> None:
        assert sanitize_cell("") == ""

    def test_tab_replaced_with_space(self) -> None:
        assert sanitize_cell("Tab\there") == "Tab here"

    def test_carriage_return_stripped(self) -> None:
        assert sanitize_cell("Line\rbreak") == "Linebreak"

    def test_newline_replaced_with_space(self) -> None:
        assert sanitize_cell("Line\nbreak") == "Line break"

    def test_mixed_control_chars(self) -> None:
        result = sanitize_cell("A\t B\r\nC")
        assert "\t" not in result
        assert "\r" not in result
        assert "\n" not in result

    def test_whitespace_stripped(self) -> None:
        assert sanitize_cell("  hello  ") == "hello"


class TestExportOutreachCsv:
    """Test CSV file export."""

    def test_writes_valid_csv(self, tmp_path: Path) -> None:
        results = [
            {
                "name": "Studio A",
                "email": "info@studioa.com",
                "phone": "555-1234",
                "source_url": "https://studioa.com",
                "venue_type": "Recording Studio",
            }
        ]
        output = tmp_path / "outreach.csv"
        count = export_outreach_csv(results, output)

        assert count == 1
        assert output.exists()

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["name"] == "Studio A"
        assert rows[0]["email"] == "info@studioa.com"

    def test_skips_venues_without_contact(self, tmp_path: Path) -> None:
        results = [
            {"name": "No Contact Venue", "email": None, "phone": None, "source_url": "https://example.com"},
            {"name": "Has Email", "email": "a@b.com", "phone": None, "source_url": "https://hasemail.com"},
        ]
        output = tmp_path / "outreach.csv"
        count = export_outreach_csv(results, output)

        assert count == 1
        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["name"] == "Has Email"

    def test_header_only_on_empty_results(self, tmp_path: Path) -> None:
        output = tmp_path / "outreach.csv"
        count = export_outreach_csv([], output)

        assert count == 0
        assert output.exists()
        with open(output) as f:
            lines = f.readlines()
        # Only header line
        assert len(lines) == 1
        assert "name" in lines[0]

    def test_sanitizes_cell_values(self, tmp_path: Path) -> None:
        results = [
            {
                "name": "=EVIL",
                "email": "safe@email.com",
                "phone": "555-0000",
                "source_url": "https://evil.com",
                "venue_type": "-dangerous",
            }
        ]
        output = tmp_path / "outreach.csv"
        export_outreach_csv(results, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["name"] == "'=EVIL"
        assert rows[0]["venue_type"] == "'-dangerous"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        output = tmp_path / "nested" / "dir" / "outreach.csv"
        results = [{"name": "Test", "email": "t@t.com", "phone": None, "source_url": "https://t.com"}]
        count = export_outreach_csv(results, output)

        assert count == 1
        assert output.exists()

    def test_uses_source_url_for_website(self, tmp_path: Path) -> None:
        results = [
            {"name": "Venue", "email": "v@v.com", "phone": None, "source_url": "https://venue.com", "website": None}
        ]
        output = tmp_path / "outreach.csv"
        export_outreach_csv(results, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["website"] == "https://venue.com"
