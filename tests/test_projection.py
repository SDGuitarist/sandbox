"""Verify-first tests: projection merge semantics (patch/partial-update contract)."""
import pytest

from app.db import append_event, get_projection, init_db


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path=path)
    return path


def test_projection_merge_patch_semantics(db):
    """Three sequential events, each partial-update; final state is shallow merge."""
    append_event("u1", "user", "created", {"name": "Alice", "email": "a@x.com"}, db_path=db)
    append_event("u1", "user", "email_changed", {"email": "b@x.com"}, db_path=db)
    append_event("u1", "user", "role_added", {"role": "admin"}, db_path=db)

    proj = get_projection("u1", db_path=db)
    assert proj is not None
    assert proj["state"] == {"name": "Alice", "email": "b@x.com", "role": "admin"}
    assert proj["version"] == 3


def test_projection_version_increments(db):
    for i in range(5):
        append_event("e1", "order", "updated", {"step": i}, db_path=db)
    proj = get_projection("e1", db_path=db)
    assert proj["version"] == 5


def test_projection_key_overwrite(db):
    """Later event overwrites key from earlier event."""
    append_event("e2", "item", "created", {"status": "pending", "count": 1}, db_path=db)
    append_event("e2", "item", "updated", {"status": "active"}, db_path=db)

    proj = get_projection("e2", db_path=db)
    assert proj["state"]["status"] == "active"
    assert proj["state"]["count"] == 1  # unchanged from first event


def test_projection_none_for_unknown_entity(db):
    assert get_projection("nonexistent", db_path=db) is None


def test_projection_entity_type_stored(db):
    append_event("t1", "ticket", "opened", {"title": "Bug"}, db_path=db)
    proj = get_projection("t1", db_path=db)
    assert proj["entity_type"] == "ticket"


def test_first_event_creates_projection(db):
    append_event("new1", "widget", "created", {"color": "blue"}, db_path=db)
    proj = get_projection("new1", db_path=db)
    assert proj is not None
    assert proj["version"] == 1
    assert proj["state"] == {"color": "blue"}
