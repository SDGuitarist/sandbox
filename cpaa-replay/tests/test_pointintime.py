import json
import os
import sqlite3
import tempfile
import uuid

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_SHADOW_SCHEMA = os.path.join(_PROJECT_ROOT, "schema", "shadow_schema.sql")
_LIVE_SCHEMA = os.path.join(_PROJECT_ROOT, "schema", "live_schema.sql")


def _canon(payload):
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _apply_schema(path, sql_file):
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA journal_mode=WAL")
    raw.execute("PRAGMA foreign_keys=ON")
    with open(sql_file, "r", encoding="utf-8") as fh:
        raw.executescript(fh.read())
    raw.close()


def _apply_live_schema(path):
    raw = sqlite3.connect(path)
    with open(_LIVE_SCHEMA, "r", encoding="utf-8") as fh:
        raw.executescript(fh.read())
    raw.commit()
    raw.close()


@pytest.fixture
def env_dbs():
    live_fd, live_path = tempfile.mkstemp(suffix="_live.db")
    shadow_fd, shadow_path = tempfile.mkstemp(suffix="_shadow.db")
    os.close(live_fd)
    os.close(shadow_fd)

    _apply_live_schema(live_path)
    _apply_schema(shadow_path, _SHADOW_SCHEMA)

    os.environ["LIVE_DB"] = live_path
    os.environ["SHADOW_DB"] = shadow_path
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    os.environ.setdefault("APP_PASSWORD", "test-password")

    yield {"live": live_path, "shadow": shadow_path}

    for p in (live_path, shadow_path):
        try:
            os.unlink(p)
        except OSError:
            pass


@pytest.fixture
def app(env_dbs):
    from app import create_app

    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client):
    page = client.get("/auth/login")
    html = page.get_data(as_text=True)
    token = _extract_csrf(html)
    client.post(
        "/auth/login",
        data={"password": os.environ["APP_PASSWORD"], "csrf_token": token},
    )
    return token


def _extract_csrf(html):
    marker = 'name="csrf_token"'
    idx = html.find(marker)
    if idx == -1:
        return ""
    value_marker = 'value="'
    vidx = html.find(value_marker, idx)
    if vidx == -1:
        return ""
    start = vidx + len(value_marker)
    end = html.find('"', start)
    return html[start:end]


# Three controlled events at distinct, ordered timestamps.
_T1 = "2026-06-15 18:00:00"
_T2 = "2026-06-15 19:00:00"
_T3 = "2026-06-15 20:00:00"
_EARLIEST = _T1
_LATEST = _T3
_BEFORE_EARLIEST = "2026-06-15 17:00:00"
_AFTER_LATEST = "2026-06-15 23:00:00"


def _seed_events():
    from app.db import get_db
    from app.event_models import append_event

    events = [
        (_T1, "system.heartbeat", {"station_id": "S1"}),
        (_T2, "telemetry.culinary.weight", {"station_id": "S1", "weight_kg": 12.5}),
        (_T3, "telemetry.financial.bid", {"lot_id": "L1", "amount_cents": 5000}),
    ]
    with get_db(immediate=True) as conn:
        for logical_ts, event_type, payload in events:
            append_event(
                conn,
                uuid.uuid4().hex,
                logical_ts,
                event_type,
                _canon(payload),
                "test",
            )


def test_events_at_time_inclusive(app):
    """WHEN an event's logical_ts equals t exactly THE SYSTEM SHALL include it (inclusive <=)."""
    with app.app_context():
        _seed_events()
        from app.db import get_db
        from app.event_models import events_at_time

        with get_db() as conn:
            at_t2 = events_at_time(conn, _T2)
            timestamps = [row["logical_ts"] for row in at_t2]

    # _T2 is included (inclusive), _T3 (after) is not.
    assert _T2 in timestamps
    assert _T3 not in timestamps
    assert _T1 in timestamps


def test_events_at_time_ordered_by_event_id(app):
    """events_at_time ORDER BY event_id (monotonic), not arrival/logical_ts."""
    with app.app_context():
        _seed_events()
        from app.db import get_db
        from app.event_models import events_at_time, get_events

        with get_db() as conn:
            pit = events_at_time(conn, _LATEST)
            full = get_events(conn)

    pit_ids = [row["event_id"] for row in pit]
    full_ids = [row["event_id"] for row in full]
    # Identical ORDER BY between point-in-time (at latest) and full scan.
    assert pit_ids == full_ids
    assert pit_ids == sorted(pit_ids)


def test_before_earliest_empty_projection(app):
    """WHEN t is before the earliest event THE SYSTEM SHALL return an empty projection."""
    with app.app_context():
        _seed_events()
        from app.db import get_db
        from app.replay_engine import build_projection_at

        with get_db() as conn:
            proj = build_projection_at(conn, _BEFORE_EARLIEST)

    # Every projection table is present but empty.
    for table in ("station_state", "auction_state", "environmental_state", "system_state"):
        assert proj.get(table, {}) == {}


def test_inclusive_boundary_includes_equal_ts(app):
    """An event whose logical_ts == t is reflected in the projection at t."""
    with app.app_context():
        _seed_events()
        from app.db import get_db
        from app.replay_engine import build_projection_at

        with get_db() as conn:
            # At exactly _T1, the S1 heartbeat (logical_ts == _T1) must be applied.
            proj_at_t1 = build_projection_at(conn, _T1)
            # Just before _T1 there is nothing.
            proj_before = build_projection_at(conn, _BEFORE_EARLIEST)

    assert "S1" in proj_at_t1.get("station_state", {})
    assert proj_before.get("station_state", {}) == {}


def test_after_latest_equals_full_replay(app, client):
    """WHEN t is at/after the latest event THE SYSTEM SHALL match a full replay."""
    with app.app_context():
        _seed_events()

    # Trigger a full replay via the route so the shadow projection tables are populated.
    _login(client)
    page = client.get("/auth/login")
    token = _extract_csrf(page.get_data(as_text=True))
    resp = client.post("/replay/run", headers={"X-CSRFToken": token})
    assert resp.status_code in (200, 302)

    with app.app_context():
        from app.db import get_db
        from app.replay_engine import build_projection_at

        with get_db() as conn:
            pit_after = build_projection_at(conn, _AFTER_LATEST)
            pit_at_latest = build_projection_at(conn, _LATEST)
            full = _read_projection_tables(conn)

    # build_projection_at after the latest event == build at exactly the latest event.
    assert pit_after == pit_at_latest
    # And it matches the full replay materialized in the shadow projection tables.
    assert pit_after == full


def _read_projection_tables(conn):
    """Read shadow projection tables into the same {table: {pk: row_dict}} shape
    that build_projection_at returns."""
    result = {}
    table_pk = {
        "station_state": "station_id",
        "auction_state": "lot_id",
        "environmental_state": "id",
        "system_state": "k",
    }
    for table, pk in table_pk.items():
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        result[table] = {str(row[pk]): dict(row) for row in rows}
    return result
