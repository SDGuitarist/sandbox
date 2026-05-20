"""Tests for LeadModel Pydantic validation at the ingest boundary."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from pydantic import ValidationError

from ingest import LeadModel


def _valid_dict(**overrides):
    """Minimal valid lead dict."""
    base = {
        "name": "Jane Doe",
        "bio": None,
        "location": None,
        "email": None,
        "phone": None,
        "website": None,
        "profile_url": "https://example.com/jane",
        "activity": None,
        "source": "eventbrite",
    }
    base.update(overrides)
    return base


def test_valid_dict_passes():
    lead = LeadModel.model_validate(_valid_dict())
    assert lead.name == "Jane Doe"
    assert lead.source == "eventbrite"


def test_model_dump_returns_clean_dict():
    lead = LeadModel.model_validate(_valid_dict(phone="555-1234"))
    d = lead.model_dump()
    assert isinstance(d, dict)
    assert d["phone"] == "555-1234"
    assert d["bio"] is None


def test_missing_name_fails():
    with pytest.raises(ValidationError) as exc_info:
        LeadModel.model_validate(_valid_dict(name=None))
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("name",) for e in errors)


def test_empty_name_fails():
    with pytest.raises(ValidationError):
        LeadModel.model_validate(_valid_dict(name=""))


def test_empty_profile_url_fails():
    with pytest.raises(ValidationError):
        LeadModel.model_validate(_valid_dict(profile_url=""))


def test_non_https_profile_url_fails():
    with pytest.raises(ValidationError) as exc_info:
        LeadModel.model_validate(_valid_dict(profile_url="http://example.com"))
    errors = exc_info.value.errors()
    assert any("https" in e["msg"] for e in errors)


def test_null_source_fails():
    with pytest.raises(ValidationError) as exc_info:
        LeadModel.model_validate(_valid_dict(source=None))
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("source",) for e in errors)


def test_empty_source_fails():
    with pytest.raises(ValidationError):
        LeadModel.model_validate(_valid_dict(source=""))


def test_strict_mode_rejects_int_as_name():
    """ConfigDict(strict=True) prevents silent type coercion."""
    with pytest.raises(ValidationError):
        LeadModel.model_validate(_valid_dict(name=123))


def test_optional_fields_accept_none():
    lead = LeadModel.model_validate(_valid_dict())
    assert lead.bio is None
    assert lead.email is None
    assert lead.phone is None
    assert lead.website is None
    assert lead.activity is None


def test_optional_fields_accept_missing_keys():
    """Dict without optional keys still validates (defaults to None)."""
    minimal = {
        "name": "Jane",
        "profile_url": "https://example.com/jane",
        "source": "eventbrite",
    }
    lead = LeadModel.model_validate(minimal)
    assert lead.bio is None
    assert lead.phone is None
