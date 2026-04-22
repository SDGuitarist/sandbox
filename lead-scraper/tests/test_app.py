"""Tests for Flask routes: filter composition, export, pagination, delete."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from db import init_db, get_db, DB_PATH
from ingest import ingest_leads


def _seed_db():
    """Insert test leads covering multiple sources and names."""
    init_db()
    leads = [
        {"name": "Alice Film", "bio": None, "location": "San Diego", "email": None, "website": None,
         "profile_url": "https://example.com/alice", "activity": None, "source": "meetup"},
        {"name": "Bob Music", "bio": None, "location": "San Diego", "email": None, "website": None,
         "profile_url": "https://example.com/bob", "activity": None, "source": "eventbrite"},
        {"name": "Alice Photo", "bio": None, "location": "LA", "email": None, "website": None,
         "profile_url": "https://example.com/alice2", "activity": None, "source": "eventbrite"},
        {"name": "Charlie Design", "bio": None, "location": "San Diego", "email": None, "website": None,
         "profile_url": "https://example.com/charlie", "activity": None, "source": "meetup"},
    ]
    ingest_leads(leads)


def _cleanup():
    if DB_PATH.exists():
        DB_PATH.unlink()


def _client():
    _cleanup()
    _seed_db()
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


# --- Filter composition ---

def test_filter_by_source_only():
    client = _client()
    resp = client.get("/?source=meetup")
    assert resp.status_code == 200
    assert b"Alice Film" in resp.data
    assert b"Charlie Design" in resp.data
    assert b"Bob Music" not in resp.data
    _cleanup()


def test_filter_by_query_only():
    client = _client()
    resp = client.get("/?q=Alice")
    assert resp.status_code == 200
    assert b"Alice Film" in resp.data
    assert b"Alice Photo" in resp.data
    assert b"Bob Music" not in resp.data
    _cleanup()


def test_filter_combined_source_and_query():
    """q + source must compose: Alice AND eventbrite = only Alice Photo."""
    client = _client()
    resp = client.get("/?q=Alice&source=eventbrite")
    assert resp.status_code == 200
    assert b"Alice Photo" in resp.data
    assert b"Alice Film" not in resp.data  # Alice but meetup, not eventbrite
    assert b"Bob Music" not in resp.data   # eventbrite but not Alice
    _cleanup()


# --- Filtered total and pagination ---

def test_filtered_total_matches_filter():
    """Total count in the page should reflect filtered results, not all leads."""
    client = _client()
    resp = client.get("/?source=meetup")
    # 2 meetup leads out of 4 total
    assert b"2 leads" in resp.data
    _cleanup()


# --- CSV export respects filters ---

def test_export_all():
    client = _client()
    resp = client.get("/leads/export.csv")
    lines = resp.data.decode().strip().split("\n")
    assert len(lines) == 5  # header + 4 leads
    _cleanup()


def test_export_filtered_by_source():
    client = _client()
    resp = client.get("/leads/export.csv?source=meetup")
    lines = resp.data.decode().strip().split("\n")
    assert len(lines) == 3  # header + 2 meetup leads
    _cleanup()


def test_export_filtered_combined():
    """Export with q + source should only include matching leads."""
    client = _client()
    resp = client.get("/leads/export.csv?q=Alice&source=eventbrite")
    lines = resp.data.decode().strip().split("\n")
    assert len(lines) == 2  # header + 1 (Alice Photo)
    _cleanup()


# --- Delete route ---

def test_delete_lead_with_csrf_header():
    """POST with X-Requested-With header should delete and return 204."""
    client = _client()
    with get_db() as conn:
        lead = conn.execute("SELECT id FROM leads LIMIT 1").fetchone()
    lead_id = lead["id"]

    resp = client.post(
        f"/leads/{lead_id}/delete",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 204

    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM leads WHERE id = ?", (lead_id,)).fetchone()[0]
    assert count == 0
    _cleanup()


def test_delete_blocked_without_csrf_header():
    """POST without X-Requested-With header should return 403."""
    client = _client()
    with get_db() as conn:
        lead = conn.execute("SELECT id FROM leads LIMIT 1").fetchone()
    lead_id = lead["id"]

    resp = client.post(f"/leads/{lead_id}/delete")
    assert resp.status_code == 403

    # Lead should still exist
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM leads WHERE id = ?", (lead_id,)).fetchone()[0]
    assert count == 1
    _cleanup()
