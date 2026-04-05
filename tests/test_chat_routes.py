"""Integration tests for all chat room API routes."""
import pytest

from chat.app import create_app
from chat.db import join_room, post_message


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, db_path


# ── POST /rooms ───────────────────────────────────────────────────────────────

def test_create_room_201(client):
    c, _ = client
    resp = c.post("/rooms", json={"name": "general", "created_by": "alice"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "general"
    assert data["created_by"] == "alice"
    assert "id" in data and "created_at" in data


def test_create_room_missing_fields_400(client):
    c, _ = client
    resp = c.post("/rooms", json={"name": "general"})
    assert resp.status_code == 400


def test_create_room_duplicate_409(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    resp = c.post("/rooms", json={"name": "general", "created_by": "bob"})
    assert resp.status_code == 409


def test_create_room_no_json_400(client):
    c, _ = client
    resp = c.post("/rooms", data="not json", content_type="text/plain")
    assert resp.status_code == 400


# ── GET /rooms ────────────────────────────────────────────────────────────────

def test_list_rooms(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    c.post("/rooms", json={"name": "random", "created_by": "bob"})
    resp = c.get("/rooms")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["rooms"]) == 2


def test_list_rooms_empty(client):
    c, _ = client
    resp = c.get("/rooms")
    assert resp.status_code == 200
    assert resp.get_json()["rooms"] == []


# ── POST /rooms/<id>/join ─────────────────────────────────────────────────────

def test_join_room_200(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    resp = c.post("/rooms/1/join", json={"user_id": "bob"})
    assert resp.status_code == 200
    assert resp.get_json()["joined"] is True


def test_join_room_already_member(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    c.post("/rooms/1/join", json={"user_id": "bob"})
    resp = c.post("/rooms/1/join", json={"user_id": "bob"})
    assert resp.status_code == 200
    assert resp.get_json()["joined"] is False


def test_join_room_not_found_404(client):
    c, _ = client
    resp = c.post("/rooms/999/join", json={"user_id": "bob"})
    assert resp.status_code == 404


def test_join_room_missing_user_id_400(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    resp = c.post("/rooms/1/join", json={})
    assert resp.status_code == 400


# ── POST /rooms/<id>/leave ────────────────────────────────────────────────────

def test_leave_room_200(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    c.post("/rooms/1/join", json={"user_id": "bob"})
    resp = c.post("/rooms/1/leave", json={"user_id": "bob"})
    assert resp.status_code == 200
    assert resp.get_json()["left"] is True


def test_leave_room_not_member(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    resp = c.post("/rooms/1/leave", json={"user_id": "carol"})
    assert resp.status_code == 200
    assert resp.get_json()["left"] is False


def test_leave_room_not_found_404(client):
    c, _ = client
    resp = c.post("/rooms/999/leave", json={"user_id": "bob"})
    assert resp.status_code == 404


# ── POST /rooms/<id>/messages ─────────────────────────────────────────────────

def test_post_message_201(client):
    c, db_path = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    c.post("/rooms/1/join", json={"user_id": "alice"})
    resp = c.post("/rooms/1/messages", json={"user_id": "alice", "content": "Hello!"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["content"] == "Hello!"
    assert data["user_id"] == "alice"
    assert data["room_id"] == 1


def test_post_message_non_member_403(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    resp = c.post("/rooms/1/messages", json={"user_id": "bob", "content": "Hi"})
    assert resp.status_code == 403


def test_post_message_room_not_found_404(client):
    c, _ = client
    resp = c.post("/rooms/999/messages", json={"user_id": "alice", "content": "Hi"})
    assert resp.status_code == 404


def test_post_message_missing_fields_400(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    c.post("/rooms/1/join", json={"user_id": "alice"})
    resp = c.post("/rooms/1/messages", json={"user_id": "alice"})
    assert resp.status_code == 400


def test_post_message_content_too_long_400(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    c.post("/rooms/1/join", json={"user_id": "alice"})
    resp = c.post("/rooms/1/messages", json={"user_id": "alice", "content": "x" * 2001})
    assert resp.status_code == 400


def test_post_message_rate_limited_429(client):
    c, db_path = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    c.post("/rooms/1/join", json={"user_id": "alice"})
    # Post 20 messages (the limit)
    for _ in range(20):
        r = c.post("/rooms/1/messages", json={"user_id": "alice", "content": "msg"})
        assert r.status_code == 201
    # 21st should be rate limited
    resp = c.post("/rooms/1/messages", json={"user_id": "alice", "content": "one more"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_post_message_whitespace_user_id_400(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    resp = c.post("/rooms/1/messages", json={"user_id": "   ", "content": "hello"})
    assert resp.status_code == 400


def test_post_message_user_id_too_long_400(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    resp = c.post("/rooms/1/messages", json={"user_id": "x" * 65, "content": "hello"})
    assert resp.status_code == 400


def test_create_room_name_too_long_400(client):
    c, _ = client
    resp = c.post("/rooms", json={"name": "x" * 101, "created_by": "alice"})
    assert resp.status_code == 400


# ── GET /rooms/<id>/messages ──────────────────────────────────────────────────

def test_get_messages_200(client):
    c, db_path = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    join_room(1, "alice", db_path=db_path)
    for i in range(3):
        post_message(1, "alice", f"msg {i}", db_path=db_path)

    resp = c.get("/rooms/1/messages")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["messages"]) == 3
    assert data["next_cursor"] is None


def test_get_messages_cursor_pagination(client):
    c, db_path = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    join_room(1, "alice", db_path=db_path)
    for i in range(5):
        post_message(1, "alice", f"msg {i}", db_path=db_path)

    resp1 = c.get("/rooms/1/messages?limit=3")
    data1 = resp1.get_json()
    assert len(data1["messages"]) == 3
    cursor = data1["next_cursor"]
    assert cursor is not None

    resp2 = c.get(f"/rooms/1/messages?after={cursor}&limit=3")
    data2 = resp2.get_json()
    assert len(data2["messages"]) == 2
    assert data2["next_cursor"] is None

    all_ids = [m["id"] for m in data1["messages"] + data2["messages"]]
    assert all_ids == sorted(all_ids)
    assert len(all_ids) == 5


def test_get_messages_room_not_found_404(client):
    c, _ = client
    resp = c.get("/rooms/999/messages")
    assert resp.status_code == 404


def test_get_messages_invalid_limit_400(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    resp = c.get("/rooms/1/messages?limit=abc")
    assert resp.status_code == 400


def test_get_messages_invalid_cursor_400(client):
    c, _ = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    resp = c.get("/rooms/1/messages?after=xyz")
    assert resp.status_code == 400


def test_get_messages_after_filters_correctly(client):
    c, db_path = client
    c.post("/rooms", json={"name": "general", "created_by": "alice"})
    join_room(1, "alice", db_path=db_path)
    m1 = post_message(1, "alice", "first", db_path=db_path)
    post_message(1, "alice", "second", db_path=db_path)

    resp = c.get(f"/rooms/1/messages?after={m1['id']}")
    data = resp.get_json()
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "second"
