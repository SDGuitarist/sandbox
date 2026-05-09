"""Tests for restricted natural-language workflow translation."""

import json
import sys
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import run


def test_parse_nl_status_request():
    plan = run._parse_nl_request("show database status")

    assert plan["action"] == "status"
    assert plan["mutations"] == []
    assert plan["needs_lock"] is False


def test_parse_nl_scrape_with_keywords_uses_safe_defaults():
    plan = run._parse_nl_request(
        "let's scrape filmmaker leads with keywords composer, colorist, and editor"
    )

    assert plan["action"] == "scrape-only"
    assert plan["location"] == "San Diego, CA"
    assert plan["mutations"] == [
        {
            "source_name": "eventbrite",
            "field_name": "keywords",
            "items": ["composer", "colorist", "editor"],
        }
    ]


def test_parse_nl_add_instagram_hashtags():
    plan = run._parse_nl_request(
        "add instagram hashtags #SDColorist, #SanDiegoColorGrading"
    )

    assert plan["action"] == "config-only"
    assert plan["mutations"] == [
        {
            "source_name": "instagram",
            "field_name": "hashtags",
            "items": ["SDColorist", "SanDiegoColorGrading"],
        }
    ]


def test_parse_nl_add_facebook_groups():
    plan = run._parse_nl_request(
        "add facebook groups https://www.facebook.com/groups/testone/, https://www.facebook.com/groups/testtwo/"
    )

    assert plan["action"] == "config-only"
    assert plan["mutations"] == [
        {
            "source_name": "facebook",
            "field_name": "groups",
            "items": [
                "https://www.facebook.com/groups/testone/",
                "https://www.facebook.com/groups/testtwo/",
            ],
        }
    ]


def test_cmd_nl_adds_keywords_then_runs_workflow(monkeypatch, tmp_path):
    overrides_path = tmp_path / "sources.overrides.json"
    monkeypatch.setattr(config, "SOURCES_OVERRIDES_PATH", overrides_path)
    audit_path = tmp_path / "nl_audit.jsonl"
    monkeypatch.setattr(run, "NL_AUDIT_LOG_PATH", audit_path)

    calls = []

    def fake_cmd_workflow(args):
        calls.append(
            (
                args.action,
                args.location,
                list(config.get_sources()["eventbrite"]["keywords"][-3:]),
            )
        )

    monkeypatch.setattr(run, "cmd_workflow", fake_cmd_workflow)

    args = Namespace(
        text=[
            "scrape",
            "filmmaker",
            "leads",
            "with",
            "keywords",
            "composer,",
            "colorist,",
            "and",
            "editor",
        ],
        yes=True,
    )

    run.cmd_nl(args)

    assert overrides_path.exists()
    entries = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert entries[-1]["status"] == "executed"
    assert calls == [
        ("scrape-only", "San Diego, CA", ["composer", "colorist", "editor"])
    ]


def test_cmd_nl_config_only_can_cancel(monkeypatch, tmp_path, capsys):
    overrides_path = tmp_path / "sources.overrides.json"
    monkeypatch.setattr(config, "SOURCES_OVERRIDES_PATH", overrides_path)
    audit_path = tmp_path / "nl_audit.jsonl"
    monkeypatch.setattr(run, "NL_AUDIT_LOG_PATH", audit_path)
    monkeypatch.setattr("builtins.input", lambda _: "n")

    args = Namespace(text=["add", "keywords", "composer,", "editor"], yes=False, preview=False)

    run.cmd_nl(args)

    output = capsys.readouterr().out
    assert "Cancelled." in output
    assert not overrides_path.exists()
    entries = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert entries[-1]["status"] == "cancelled"


def test_cmd_nl_preview_does_not_write_or_run(monkeypatch, tmp_path):
    overrides_path = tmp_path / "sources.overrides.json"
    monkeypatch.setattr(config, "SOURCES_OVERRIDES_PATH", overrides_path)
    audit_path = tmp_path / "nl_audit.jsonl"
    monkeypatch.setattr(run, "NL_AUDIT_LOG_PATH", audit_path)

    called = []
    monkeypatch.setattr(run, "cmd_workflow", lambda args: called.append(args.action))

    args = Namespace(
        text=["add", "instagram", "hashtags", "#SDColorist,", "#SanDiegoColorGrading"],
        yes=False,
        preview=True,
    )

    run.cmd_nl(args)

    assert called == []
    assert not overrides_path.exists()
    entries = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert entries[-1]["status"] == "preview"


def test_eventbrite_keyword_cap_is_enforced(monkeypatch, tmp_path):
    overrides_path = tmp_path / "sources.overrides.json"
    monkeypatch.setattr(config, "SOURCES_OVERRIDES_PATH", overrides_path)

    extra = [f"extra keyword {i}" for i in range(5)]
    config.add_source_list_items("eventbrite", "keywords", extra)

    try:
        config.add_source_list_items("eventbrite", "keywords", ["one too many"])
    except ValueError as e:
        assert "cannot exceed 25 items" in str(e)
    else:
        raise AssertionError("Expected keyword cap validation to raise.")
