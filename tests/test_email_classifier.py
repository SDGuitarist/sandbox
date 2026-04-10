"""Tests for email_classifier.py — config, samples, logging, summary math."""

import json
from unittest.mock import patch

import pytest

from email_classifier import (
    EmailClassifierConfig,
    HIGH_STAKES,
    load_sample_emails,
    log_result,
    parse_classification,
    print_summary,
    RESULTS_FILE,
)


# --- Config ---


def test_config_is_frozen():
    config = EmailClassifierConfig()
    with pytest.raises(AttributeError):
        config.executor_model = "other-model"


def test_config_defaults():
    config = EmailClassifierConfig()
    assert "haiku" in config.executor_model
    assert "opus" in config.advisor_model
    assert config.max_tokens == 1024
    assert config.advisor_max_tokens == 512


# --- Sample emails ---


def test_sample_count():
    emails = load_sample_emails()
    assert len(emails) == 20


def test_sample_labels_present():
    for email in load_sample_emails():
        assert "id" in email
        assert "sender" in email
        assert "subject" in email
        assert "body" in email
        assert "ground_truth" in email
        assert "should_escalate" in email
        assert isinstance(email["should_escalate"], bool)


def test_sample_escalation_labels():
    emails = load_sample_emails()
    should_escalate = [e for e in emails if e["should_escalate"]]
    should_not = [e for e in emails if not e["should_escalate"]]
    assert len(should_escalate) == 6
    assert len(should_not) == 14


def test_sample_high_stakes_count():
    emails = load_sample_emails()
    high_stakes = [e for e in emails if e["ground_truth"] in HIGH_STAKES]
    # 7 clear high-stakes (1-7) + 2 ambiguous with high-stakes ground truth (19, 20)
    assert len(high_stakes) == 9


def test_sample_ids_unique():
    emails = load_sample_emails()
    ids = [e["id"] for e in emails]
    assert len(ids) == len(set(ids))


# --- Parse classification ---


def test_parse_clean_json():
    result = parse_classification('{"category": "gig_inquiry", "confidence": 0.9, "reasoning": "clear request"}')
    assert result["category"] == "gig_inquiry"
    assert result["confidence"] == 0.9


def test_parse_markdown_fenced():
    text = '```json\n{"category": "marketing", "confidence": 0.8, "reasoning": "promo"}\n```'
    result = parse_classification(text)
    assert result["category"] == "marketing"


def test_parse_embedded_json():
    text = 'Based on my analysis, here is the classification:\n{"category": "subscription", "confidence": 0.95, "reasoning": "newsletter"}\nThat is my assessment.'
    result = parse_classification(text)
    assert result["category"] == "subscription"


def test_parse_garbage():
    result = parse_classification("this is not json at all")
    assert result["category"] == "parse_error"


# --- Logging ---


def test_log_result_writes_jsonl(tmp_path):
    test_file = tmp_path / "test_results.jsonl"
    result = {"email_id": "test_01", "final_decision": "marketing"}

    with patch("email_classifier.RESULTS_FILE", test_file):
        log_result(result)
        log_result({"email_id": "test_02", "final_decision": "gig_inquiry"})

    lines = test_file.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["email_id"] == "test_01"
    assert json.loads(lines[1])["email_id"] == "test_02"


# --- Summary math ---


def _make_result(email_id, ground_truth, final_decision, should_escalate, escalated,
                 haiku_preliminary=None, advisor_changed=False):
    """Helper to build a minimal result dict for summary testing."""
    return {
        "email_id": email_id,
        "ground_truth": ground_truth,
        "final_decision": final_decision,
        "should_escalate": should_escalate,
        "escalated": escalated,
        "haiku_preliminary": haiku_preliminary,
        "advisor_changed_answer": advisor_changed,
        "total_cost_usd": 0.0002,
        "api_calls": 3 if escalated else 1,
        "executor_input_tokens": 500,
        "executor_output_tokens": 100,
        "advisor_input_tokens": 200 if escalated else 0,
        "advisor_output_tokens": 100 if escalated else 0,
        "latency_ms": 2000,
    }


def test_summary_accuracy(capsys):
    results = [
        _make_result("s01", "gig_inquiry", "gig_inquiry", False, False),
        _make_result("s02", "marketing", "marketing", False, False),
        _make_result("s03", "marketing", "gig_inquiry", True, True, "marketing", True),
    ]
    print_summary(results)
    out = capsys.readouterr().out
    assert "2/3 (67%)" in out


def test_summary_lead_safety(capsys):
    results = [
        _make_result("s01", "gig_inquiry", "gig_inquiry", False, False),
        _make_result("s02", "business_opportunity", "business_opportunity", False, False),
        _make_result("s03", "subscription", "subscription", False, False),
    ]
    print_summary(results)
    out = capsys.readouterr().out
    assert "2/2" in out
    assert "PASS" in out


def test_summary_escalation_matrix(capsys):
    results = [
        # TP: should escalate, did escalate
        _make_result("s01", "marketing", "marketing", True, True),
        # FN: should escalate, did NOT escalate
        _make_result("s02", "marketing", "marketing", True, False),
        # FP: should NOT escalate, did escalate
        _make_result("s03", "subscription", "subscription", False, True),
        # TN: should NOT escalate, did NOT escalate
        _make_result("s04", "gig_inquiry", "gig_inquiry", False, False),
    ]
    print_summary(results)
    out = capsys.readouterr().out
    assert "TP=1" in out
    assert "FN=1" in out
    assert "FP=1" in out
    assert "0.50" in out  # recall: 1/(1+1)


def test_summary_no_errors(capsys):
    results = [
        _make_result("s01", "gig_inquiry", "gig_inquiry", False, False),
    ]
    print_summary(results)
    out = capsys.readouterr().out
    assert "Errors" not in out
