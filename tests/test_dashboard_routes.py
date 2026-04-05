"""Integration tests for service mesh dashboard API routes."""
import pytest

from dashboard.app import create_app
from dashboard.db import get_db, init_db
from dashboard.keys import create_key
from dashboard.services import create_service
from dashboard.health import record_result
from dashboard.events import append_event


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        # Create an admin API key for use in tests
        with get_db(path=db_path, immediate=True) as conn:
            key_info = create_key(conn, label="test-admin")
        yield c, db_path, key_info["key"]


def auth(key):
    return {"Authorization": f"Bearer {key}"}


# ── POST /services ────────────────────────────────────────────────────────────

def test_create_service_201(client):
    c, db_path, key = client
    resp = c.post("/services", json={
        "name": "my-api",
        "health_check_url": "http://example.com/health",
    }, headers=auth(key))
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "my-api"


def test_create_service_no_auth_401(client):
    c, _, _ = client
    resp = c.post("/services", json={"name": "x", "health_check_url": "http://example.com/h"})
    assert resp.status_code == 401


def test_create_service_ssrf_rejected_422(client):
    c, _, key = client
    resp = c.post("/services", json={
        "name": "bad",
        "health_check_url": "http://127.0.0.1/health",
    }, headers=auth(key))
    assert resp.status_code == 422


def test_create_service_missing_name_400(client):
    c, _, key = client
    resp = c.post("/services", json={"health_check_url": "http://example.com/health"},
                  headers=auth(key))
    assert resp.status_code == 400


def test_create_service_duplicate_409(client):
    c, _, key = client
    c.post("/services", json={"name": "dup", "health_check_url": "http://example.com/h"},
           headers=auth(key))
    resp = c.post("/services", json={"name": "dup", "health_check_url": "http://example.com/h"},
                  headers=auth(key))
    assert resp.status_code == 409


def test_create_service_appends_event(client):
    c, db_path, key = client
    c.post("/services", json={"name": "evt-svc", "health_check_url": "http://example.com/h"},
           headers=auth(key))
    resp = c.get("/events")
    events = resp.get_json()["events"]
    assert any(e["event_type"] == "service.registered" for e in events)


# ── GET /services ─────────────────────────────────────────────────────────────

def test_list_services(client):
    c, _, key = client
    c.post("/services", json={"name": "s1", "health_check_url": "http://example.com/h"},
           headers=auth(key))
    c.post("/services", json={"name": "s2", "health_check_url": "http://example.com/h2"},
           headers=auth(key))
    resp = c.get("/services")
    assert resp.status_code == 200
    assert len(resp.get_json()["services"]) == 2


def test_list_services_no_key_material(client):
    c, db_path, key = client
    # Manually insert a key via DB
    with get_db(path=db_path, immediate=True) as conn:
        create_key(conn, label="exposed?")
    resp = c.get("/services")
    # Services endpoint doesn't return keys at all, but verify the key endpoint doesn't leak
    key_resp = c.get("/keys", headers=auth(key))
    for k in key_resp.get_json()["keys"]:
        assert "key" not in k
        assert "key_hash" not in k
        assert "salt" not in k


# ── GET /services/<id> ────────────────────────────────────────────────────────

def test_get_service_200(client):
    c, _, key = client
    resp = c.post("/services", json={"name": "svc", "health_check_url": "http://example.com/h"},
                  headers=auth(key))
    svc_id = resp.get_json()["id"]
    resp2 = c.get(f"/services/{svc_id}")
    assert resp2.status_code == 200
    assert "health_history" in resp2.get_json()


def test_get_service_404(client):
    c, _, _ = client
    assert c.get("/services/nonexistent").status_code == 404


# ── DELETE /services/<id> ─────────────────────────────────────────────────────

def test_delete_service_204(client):
    c, _, key = client
    resp = c.post("/services", json={"name": "del", "health_check_url": "http://example.com/h"},
                  headers=auth(key))
    svc_id = resp.get_json()["id"]
    resp2 = c.delete(f"/services/{svc_id}", headers=auth(key))
    assert resp2.status_code == 204
    assert c.get(f"/services/{svc_id}").status_code == 404


def test_delete_service_404(client):
    c, _, key = client
    assert c.delete("/services/ghost", headers=auth(key)).status_code == 404


def test_delete_service_appends_event(client):
    c, _, key = client
    resp = c.post("/services", json={"name": "gone", "health_check_url": "http://example.com/h"},
                  headers=auth(key))
    svc_id = resp.get_json()["id"]
    c.delete(f"/services/{svc_id}", headers=auth(key))
    events = c.get("/events").get_json()["events"]
    assert any(e["event_type"] == "service.deleted" for e in events)


def test_delete_service_nulls_event_service_id(client):
    """Deleting a service must SET NULL on events.service_id (not cascade-delete).

    Audit records are preserved so operators can see service.deleted events;
    service_id is cleared to break the dangling FK reference.
    """
    c, db_path, key = client
    resp = c.post("/services", json={"name": "null-me", "health_check_url": "http://example.com/h"},
                  headers=auth(key))
    svc_id = resp.get_json()["id"]
    # Confirm a registration event exists for this service
    events_before = c.get(f"/events?service_id={svc_id}").get_json()["events"]
    assert len(events_before) >= 1
    # Delete the service
    c.delete(f"/services/{svc_id}", headers=auth(key))
    # Events rows exist but service_id is now NULL
    with get_db(path=db_path) as conn:
        rows = conn.execute(
            "SELECT service_id, event_type FROM events ORDER BY id ASC"
        ).fetchall()
    # The service.registered and service.deleted events exist; their service_id is NULL
    event_types = [r["event_type"] for r in rows]
    assert "service.registered" in event_types
    assert "service.deleted" in event_types
    service_ids = [r["service_id"] for r in rows]
    assert all(sid is None for sid in service_ids)


# ── POST /services/<id>/check ─────────────────────────────────────────────────

def test_trigger_check_202(client):
    c, _, key = client
    resp = c.post("/services", json={"name": "chk", "health_check_url": "http://example.com/h"},
                  headers=auth(key))
    svc_id = resp.get_json()["id"]
    resp2 = c.post(f"/services/{svc_id}/check", headers=auth(key))
    assert resp2.status_code == 202
    assert resp2.get_json()["status"] == "queued"


# ── GET /dashboard ────────────────────────────────────────────────────────────

def test_dashboard_empty(client):
    c, _, _ = client
    resp = c.get("/dashboard")
    assert resp.status_code == 200
    assert resp.get_json()["services"] == []


def test_dashboard_with_health(client):
    c, db_path, key = client
    resp = c.post("/services", json={"name": "api", "health_check_url": "http://example.com/h"},
                  headers=auth(key))
    svc_id = resp.get_json()["id"]
    with get_db(path=db_path, immediate=True) as conn:
        record_result(conn, svc_id, "healthy", status_code=200, response_time_ms=30)
    dashboard = c.get("/dashboard").get_json()["services"]
    assert dashboard[0]["health_status"] == "healthy"
    assert dashboard[0]["last_response_ms"] == 30


# ── Keys ──────────────────────────────────────────────────────────────────────

def test_create_key_201(client):
    c, _, key = client
    resp = c.post("/keys", json={"label": "new-key"}, headers=auth(key))
    assert resp.status_code == 201
    data = resp.get_json()
    assert "key" in data  # raw key shown once


def test_create_key_missing_label_400(client):
    c, _, key = client
    assert c.post("/keys", json={}, headers=auth(key)).status_code == 400


def test_revoke_key_204(client):
    c, db_path, admin_key = client
    resp = c.post("/keys", json={"label": "to-revoke"}, headers=auth(admin_key))
    key_id = resp.get_json()["id"]
    assert c.delete(f"/keys/{key_id}", headers=auth(admin_key)).status_code == 204


def test_revoke_key_404(client):
    c, _, key = client
    assert c.delete("/keys/ghost", headers=auth(key)).status_code == 404


def test_revoked_key_rejected(client):
    c, db_path, admin_key = client
    # Create a new key and use it successfully
    resp = c.post("/keys", json={"label": "temp"}, headers=auth(admin_key))
    new_key = resp.get_json()["key"]
    new_key_id = resp.get_json()["id"]
    assert c.get("/keys", headers=auth(new_key)).status_code == 200
    # Revoke it
    c.delete(f"/keys/{new_key_id}", headers=auth(admin_key))
    # Now it should fail
    assert c.get("/keys", headers={"Authorization": f"Bearer {new_key}"}).status_code == 401


# ── GET /events ───────────────────────────────────────────────────────────────

def test_events_empty(client):
    c, _, _ = client
    resp = c.get("/events")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["events"] == []
    assert data["next_cursor"] is None


def test_events_pagination(client):
    c, db_path, key = client
    # Create 5 services to generate 5 events
    for i in range(5):
        c.post("/services", json={"name": f"s{i}", "health_check_url": "http://example.com/h"},
               headers=auth(key))
    # Fetch first 3
    resp = c.get("/events?limit=3")
    data = resp.get_json()
    assert len(data["events"]) == 3
    assert data["next_cursor"] is not None
    # Fetch rest
    cursor = data["next_cursor"]
    resp2 = c.get(f"/events?limit=3&after={cursor}")
    data2 = resp2.get_json()
    assert len(data2["events"]) >= 2
    assert data2["next_cursor"] is None


def test_events_filter_by_service(client):
    c, db_path, key = client
    r1 = c.post("/services", json={"name": "a", "health_check_url": "http://example.com/h"},
                headers=auth(key))
    r2 = c.post("/services", json={"name": "b", "health_check_url": "http://example.com/h2"},
                headers=auth(key))
    svc_id = r1.get_json()["id"]
    resp = c.get(f"/events?service_id={svc_id}")
    events = resp.get_json()["events"]
    assert all(e["service_id"] == svc_id for e in events)
