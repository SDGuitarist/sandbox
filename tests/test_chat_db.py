"""DB layer tests for the chat room API."""
import pytest

from chat.db import (
    create_room, get_messages, get_room, init_db, is_member,
    join_room, leave_room, list_rooms, post_message,
)


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path=path)
    return path


# ── Rooms ─────────────────────────────────────────────────────────────────────

def test_create_room(db):
    room = create_room("general", "alice", db_path=db)
    assert room["id"] == 1
    assert room["name"] == "general"
    assert room["created_by"] == "alice"
    assert "created_at" in room
    assert "T" not in room["created_at"]


def test_create_room_duplicate_name_raises(db):
    import sqlite3
    create_room("general", "alice", db_path=db)
    with pytest.raises(sqlite3.IntegrityError):
        create_room("general", "bob", db_path=db)


def test_list_rooms(db):
    create_room("general", "alice", db_path=db)
    create_room("random", "bob", db_path=db)
    rooms = list_rooms(db_path=db)
    assert len(rooms) == 2
    assert rooms[0]["name"] == "general"


def test_get_room_not_found(db):
    assert get_room(999, db_path=db) is None


# ── Memberships ───────────────────────────────────────────────────────────────

def test_join_room(db):
    room = create_room("general", "alice", db_path=db)
    assert join_room(room["id"], "bob", db_path=db) is True


def test_join_room_already_member(db):
    room = create_room("general", "alice", db_path=db)
    join_room(room["id"], "bob", db_path=db)
    assert join_room(room["id"], "bob", db_path=db) is False


def test_leave_room(db):
    room = create_room("general", "alice", db_path=db)
    join_room(room["id"], "bob", db_path=db)
    assert leave_room(room["id"], "bob", db_path=db) is True


def test_leave_room_not_member(db):
    room = create_room("general", "alice", db_path=db)
    assert leave_room(room["id"], "bob", db_path=db) is False


def test_is_member(db):
    room = create_room("general", "alice", db_path=db)
    assert is_member(room["id"], "alice", db_path=db) is False
    join_room(room["id"], "alice", db_path=db)
    assert is_member(room["id"], "alice", db_path=db) is True


# ── Messages ──────────────────────────────────────────────────────────────────

def test_post_message(db):
    room = create_room("general", "alice", db_path=db)
    msg = post_message(room["id"], "alice", "hello", db_path=db)
    assert msg["id"] == 1
    assert msg["content"] == "hello"
    assert msg["user_id"] == "alice"
    assert "T" not in msg["created_at"]


def test_get_messages_empty(db):
    room = create_room("general", "alice", db_path=db)
    msgs, cursor = get_messages(room["id"], db_path=db)
    assert msgs == []
    assert cursor is None


def test_get_messages_pagination(db):
    room = create_room("general", "alice", db_path=db)
    for i in range(5):
        post_message(room["id"], "alice", f"msg {i}", db_path=db)

    page1, cursor = get_messages(room["id"], limit=3, db_path=db)
    assert len(page1) == 3
    assert cursor is not None
    assert cursor == page1[2]["id"]

    page2, cursor2 = get_messages(room["id"], after_id=cursor, limit=3, db_path=db)
    assert len(page2) == 2
    assert cursor2 is None

    all_ids = [m["id"] for m in page1 + page2]
    assert all_ids == sorted(all_ids)
    assert len(all_ids) == 5


def test_get_messages_after_id(db):
    room = create_room("general", "alice", db_path=db)
    for i in range(3):
        post_message(room["id"], "alice", f"msg {i}", db_path=db)

    msgs, _ = get_messages(room["id"], after_id=1, db_path=db)
    assert all(m["id"] > 1 for m in msgs)
    assert len(msgs) == 2
