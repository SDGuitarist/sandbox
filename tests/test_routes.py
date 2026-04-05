"""Integration tests for all 5 Flask routes using a real SQLite DB."""
import pytest

from app.app import create_app
from app.db import append_event


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, db_path


# ── POST /events ─────────────────────────────────────────────────────────────

def test_post_event_returns_201(client):
    c, _ = client
    resp = c.post("/events", json={
        "entity_id": "u1", "entity_type": "user",
        "event_type": "created", "payload": {"name": "Alice"},
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["entity_id"] == "u1"
    assert data["payload"] == {"name": "Alice"}
    assert "created_at" in data


def test_post_event_missing_field_returns_400(client):
    c, _ = client
    resp = c.post("/events", json={
        "entity_id": "u1", "entity_type": "user",
        # missing event_type and payload
    })
    assert resp.status_code == 400


def test_post_event_payload_not_dict_returns_400(client):
    c, _ = client
    resp = c.post("/events", json={
        "entity_id": "u1", "entity_type": "user",
        "event_type": "created", "payload": "a string",
    })
    assert resp.status_code == 400


def test_post_event_no_json_returns_400(client):
    c, _ = client
    resp = c.post("/events", data="not json", content_type="text/plain")
    assert resp.status_code == 400


def test_post_event_actor_int_stored_as_string(client):
    c, _ = client
    resp = c.post("/events", json={
        "entity_id": "u1", "entity_type": "user",
        "event_type": "login", "payload": {}, "actor": 42,
    })
    assert resp.status_code == 201
    assert resp.get_json()["actor"] == "42"


# ── GET /events ───────────────────────────────────────────────────────────────

def test_get_events_all(client):
    c, db_path = client
    append_event("u1", "user", "login", {}, db_path=db_path)
    append_event("u2", "user", "login", {}, db_path=db_path)

    resp = c.get("/events")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["events"]) == 2
    assert data["next_cursor"] is None


def test_get_events_filter_entity_id(client):
    c, db_path = client
    append_event("u1", "user", "login", {}, db_path=db_path)
    append_event("u2", "user", "login", {}, db_path=db_path)

    resp = c.get("/events?entity_id=u1")
    data = resp.get_json()
    assert len(data["events"]) == 1
    assert data["events"][0]["entity_id"] == "u1"


def test_get_events_cursor_pagination(client):
    c, db_path = client
    for i in range(5):
        append_event("e1", "order", "step", {"i": i}, db_path=db_path)

    resp1 = c.get("/events?entity_id=e1&limit=3")
    data1 = resp1.get_json()
    assert len(data1["events"]) == 3
    cursor = data1["next_cursor"]
    assert cursor is not None

    resp2 = c.get(f"/events?entity_id=e1&after={cursor}&limit=3")
    data2 = resp2.get_json()
    assert len(data2["events"]) == 2
    assert data2["next_cursor"] is None


def test_get_events_cursor_no_rows_skipped(client):
    """Verify cursor returns correct IDs with no rows dropped."""
    c, db_path = client
    for i in range(5):
        append_event("e2", "order", "step", {"i": i}, db_path=db_path)

    resp1 = c.get("/events?entity_id=e2&limit=3")
    page1_ids = [e["id"] for e in resp1.get_json()["events"]]
    cursor = resp1.get_json()["next_cursor"]

    resp2 = c.get(f"/events?entity_id=e2&after={cursor}&limit=3")
    page2_ids = [e["id"] for e in resp2.get_json()["events"]]

    all_ids = page1_ids + page2_ids
    assert all_ids == sorted(all_ids)
    assert len(all_ids) == 5  # all 5 rows, none dropped


def test_get_events_time_range(client):
    c, db_path = client
    e1 = append_event("t1", "x", "a", {}, db_path=db_path)
    ts = e1["created_at"]
    append_event("t1", "x", "b", {}, db_path=db_path)

    resp = c.get(f"/events?entity_id=t1&since={ts}")
    data = resp.get_json()
    assert len(data["events"]) == 2  # ts itself is included (>=)


def test_get_events_invalid_since_returns_400(client):
    c, _ = client
    resp = c.get("/events?since=2026-01-01T00:00:00Z")
    assert resp.status_code == 400


def test_get_events_invalid_before_returns_400(client):
    c, _ = client
    resp = c.get("/events?before=not-a-date")
    assert resp.status_code == 400


def test_get_events_invalid_limit(client):
    c, _ = client
    resp = c.get("/events?limit=abc")
    assert resp.status_code == 400


def test_get_events_invalid_cursor(client):
    c, _ = client
    resp = c.get("/events?after=notanumber")
    assert resp.status_code == 400


# ── GET /entities/<id>/events ─────────────────────────────────────────────────

def test_entity_events_shorthand(client):
    c, db_path = client
    append_event("u1", "user", "login", {}, db_path=db_path)
    append_event("u1", "user", "logout", {}, db_path=db_path)
    append_event("u2", "user", "login", {}, db_path=db_path)

    resp = c.get("/entities/u1/events")
    data = resp.get_json()
    assert len(data["events"]) == 2
    assert all(e["entity_id"] == "u1" for e in data["events"])


# ── GET /entities/<id>/projection ─────────────────────────────────────────────

def test_projection_returns_merged_state(client):
    c, db_path = client
    append_event("u1", "user", "created", {"name": "Alice", "email": "a@x.com"}, db_path=db_path)
    append_event("u1", "user", "updated", {"email": "b@x.com"}, db_path=db_path)

    resp = c.get("/entities/u1/projection")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["state"] == {"name": "Alice", "email": "b@x.com"}
    assert data["version"] == 2


def test_projection_unknown_entity_returns_404(client):
    c, _ = client
    resp = c.get("/entities/unknown-xyz/projection")
    assert resp.status_code == 404


# ── GET /entities/<id>/history ────────────────────────────────────────────────

def test_history_returns_all_events_ascending(client):
    c, db_path = client
    for i in range(4):
        append_event("h1", "order", f"step_{i}", {"i": i}, db_path=db_path)

    resp = c.get("/entities/h1/history")
    assert resp.status_code == 200
    data = resp.get_json()
    events = data["events"]
    assert len(events) == 4
    ids = [e["id"] for e in events]
    assert ids == sorted(ids)


def test_history_empty_entity(client):
    c, _ = client
    resp = c.get("/entities/nobody/history")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["events"] == []
