"""Tests for Flask routes: filter composition, export, pagination, delete."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from db import init_db, get_db
from ingest import ingest_leads


def _seed_db(db_path):
    """Insert test leads covering multiple sources and names."""
    init_db(db_path)
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
    ingest_leads(leads, db_path)


def _client(tmp_path):
    db_path = tmp_path / "app-test.db"
    _seed_db(db_path)
    app = create_app(db_path)
    app.config["TESTING"] = True
    return app.test_client(), db_path


# --- Filter composition ---

def test_filter_by_source_only(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/?source=meetup")
    assert resp.status_code == 200
    assert b"Alice Film" in resp.data
    assert b"Charlie Design" in resp.data
    assert b"Bob Music" not in resp.data


def test_filter_by_query_only(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/?q=Alice")
    assert resp.status_code == 200
    assert b"Alice Film" in resp.data
    assert b"Alice Photo" in resp.data
    assert b"Bob Music" not in resp.data


def test_filter_combined_source_and_query(tmp_path):
    """q + source must compose: Alice AND eventbrite = only Alice Photo."""
    client, _ = _client(tmp_path)
    resp = client.get("/?q=Alice&source=eventbrite")
    assert resp.status_code == 200
    assert b"Alice Photo" in resp.data
    assert b"Alice Film" not in resp.data  # Alice but meetup, not eventbrite
    assert b"Bob Music" not in resp.data   # eventbrite but not Alice


# --- Filtered total and pagination ---

def test_filtered_total_matches_filter(tmp_path):
    """Total count in the page should reflect filtered results, not all leads."""
    client, _ = _client(tmp_path)
    resp = client.get("/?source=meetup")
    # 2 meetup leads out of 4 total
    assert b"2 leads" in resp.data


# --- CSV export respects filters ---

def test_export_all(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/leads/export.csv")
    lines = resp.data.decode().strip().split("\n")
    assert len(lines) == 5  # header + 4 leads


def test_export_filtered_by_source(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/leads/export.csv?source=meetup")
    lines = resp.data.decode().strip().split("\n")
    assert len(lines) == 3  # header + 2 meetup leads


def test_export_filtered_combined(tmp_path):
    """Export with q + source should only include matching leads."""
    client, _ = _client(tmp_path)
    resp = client.get("/leads/export.csv?q=Alice&source=eventbrite")
    lines = resp.data.decode().strip().split("\n")
    assert len(lines) == 2  # header + 1 (Alice Photo)


# --- Delete route ---

def test_delete_lead_with_csrf_header(tmp_path):
    """POST with X-Requested-With header should delete and return 204."""
    client, db_path = _client(tmp_path)
    with get_db(db_path) as conn:
        lead = conn.execute("SELECT id FROM leads LIMIT 1").fetchone()
    lead_id = lead["id"]

    resp = client.post(
        f"/leads/{lead_id}/delete",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 204

    with get_db(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM leads WHERE id = ?", (lead_id,)).fetchone()[0]
    assert count == 0


def test_delete_blocked_without_csrf_header(tmp_path):
    """POST without X-Requested-With header should return 403."""
    client, db_path = _client(tmp_path)
    with get_db(db_path) as conn:
        lead = conn.execute("SELECT id FROM leads LIMIT 1").fetchone()
    lead_id = lead["id"]

    resp = client.post(f"/leads/{lead_id}/delete")
    assert resp.status_code == 403

    # Lead should still exist
    with get_db(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM leads WHERE id = ?", (lead_id,)).fetchone()[0]
    assert count == 1


def test_delete_nonexistent_lead(tmp_path):
    """Deleting a nonexistent lead with CSRF header should return 204, not crash."""
    client, _ = _client(tmp_path)
    resp = client.post(
        "/leads/99999/delete",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 204
