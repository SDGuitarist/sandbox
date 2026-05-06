"""Tests for resilience.py -- parse_retry_after and color constants."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from resilience import parse_retry_after


def test_parse_retry_after_caps_at_120():
    """Large values are capped at 120s to prevent hangs."""
    assert parse_retry_after("999") == 120
    assert parse_retry_after("999999") == 120
    assert parse_retry_after("60") == 60
    assert parse_retry_after("0") == 0
    assert parse_retry_after(None) == 10.0  # fallback
    assert parse_retry_after(None, fallback=5.0) == 5.0


def test_parse_retry_after_handles_non_integer():
    """Non-integer and malformed values return fallback (not crash)."""
    assert parse_retry_after("Thu, 01 Dec 2026 16:00:00 GMT") == 10.0
    assert parse_retry_after("") == 10.0
    assert parse_retry_after("abc") == 10.0
    assert parse_retry_after("-5") == 0  # negative clamped to 0
