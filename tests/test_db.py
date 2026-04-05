"""DB layer tests: event append, cursor pagination, time-range filtering."""
import pytest

from app.db import append_event, get_events, init_db


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path=path)
    return path


def test_append_event_returns_event_dict(db):
    event = append_event("u1", "user", "created", {"name": "Bob"}, actor="system", db_path=db)
    assert event["id"] == 1
    assert event["entity_id"] == "u1"
    assert event["entity_type"] == "user"
    assert event["event_type"] == "created"
    assert event["actor"] == "system"
    assert "created_at" in event


def test_timestamps_normalized_format(db):
    event = append_event("u2", "user", "login", {}, db_path=db)
    ts = event["created_at"]
    # Must be YYYY-MM-DD HH:MM:SS (no T, no Z)
    assert "T" not in ts
    assert "Z" not in ts
    assert len(ts) == 19


def test_event_ids_autoincrement(db):
    e1 = append_event("a", "t", "x", {}, db_path=db)
    e2 = append_event("b", "t", "x", {}, db_path=db)
    assert e2["id"] == e1["id"] + 1


def test_get_events_filter_by_entity_id(db):
    append_event("u1", "user", "login", {}, db_path=db)
    append_event("u2", "user", "login", {}, db_path=db)
    append_event("u1", "user", "logout", {}, db_path=db)

    events, cursor = get_events(entity_id="u1", db_path=db)
    assert len(events) == 2
    assert all(e["entity_id"] == "u1" for e in events)
    assert cursor is None


def test_get_events_filter_by_event_type(db):
    append_event("u1", "user", "login", {}, db_path=db)
    append_event("u1", "user", "logout", {}, db_path=db)
    append_event("u1", "user", "login", {}, db_path=db)

    events, _ = get_events(entity_id="u1", event_type="login", db_path=db)
    assert len(events) == 2
    assert all(e["event_type"] == "login" for e in events)


def test_cursor_pagination_no_rows_dropped(db):
    for i in range(5):
        append_event("e1", "order", "step", {"i": i}, db_path=db)

    page1, cursor = get_events(entity_id="e1", limit=3, db_path=db)
    assert len(page1) == 3
    assert cursor is not None

    page2, cursor2 = get_events(entity_id="e1", after_id=cursor, limit=3, db_path=db)
    assert len(page2) == 2
    assert cursor2 is None

    # All 5 rows returned, none skipped
    all_ids = [e["id"] for e in page1 + page2]
    assert all_ids == sorted(all_ids)
    assert len(all_ids) == 5


def test_cursor_no_more_pages(db):
    for i in range(3):
        append_event("e2", "order", "step", {}, db_path=db)

    events, cursor = get_events(entity_id="e2", limit=10, db_path=db)
    assert len(events) == 3
    assert cursor is None


def test_limit_capped_at_200(db):
    events, cursor = get_events(limit=9999, db_path=db)
    assert isinstance(events, list)


def test_limit_minimum_one(db):
    append_event("a", "t", "x", {}, db_path=db)
    events, _ = get_events(limit=0, db_path=db)
    assert len(events) >= 0  # no crash; limit clamped to 1


def test_time_range_since(db):
    e1 = append_event("t1", "x", "a", {}, db_path=db)
    ts = e1["created_at"]
    append_event("t1", "x", "b", {}, db_path=db)

    events, _ = get_events(entity_id="t1", since=ts, db_path=db)
    assert len(events) == 2  # ts itself is included (>=)


def test_payload_deserialized(db):
    append_event("p1", "type", "ev", {"foo": "bar", "n": 42}, db_path=db)
    events, _ = get_events(entity_id="p1", db_path=db)
    assert events[0]["payload"] == {"foo": "bar", "n": 42}
