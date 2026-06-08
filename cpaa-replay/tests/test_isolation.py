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


def _apply_shadow_schema(path):
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA journal_mode=WAL")
    raw.execute("PRAGMA foreign_keys=ON")
    with open(_SHADOW_SCHEMA, "r", encoding="utf-8") as fh:
        raw.executescript(fh.read())
    raw.close()


def _apply_live_schema(path):
    raw = sqlite3.connect(path)
    with open(_LIVE_SCHEMA, "r", encoding="utf-8") as fh:
        raw.executescript(fh.read())
    raw.execute(
        "INSERT INTO source_events (seq, idempotency_key, logical_ts, event_type, payload, source)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (1, "k1", "2026-06-15 18:00:00", "system.heartbeat", _canon({"station_id": "S1"}), "live"),
    )
    raw.execute(
        "INSERT INTO source_events (seq, idempotency_key, logical_ts, event_type, payload, source)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (2, "k2", "2026-06-15 19:00:00", "telemetry.financial.bid",
         _canon({"lot_id": "L1", "amount_cents": 5000}), "live"),
    )
    # Match the generator's close-out so the file can be opened immutable=1.
    raw.commit()
    raw.execute("PRAGMA journal_mode=DELETE")
    raw.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    raw.close()


@pytest.fixture
def env_dbs():
    live_fd, live_path = tempfile.mkstemp(suffix="_live.db")
    shadow_fd, shadow_path = tempfile.mkstemp(suffix="_shadow.db")
    os.close(live_fd)
    os.close(shadow_fd)

    _apply_live_schema(live_path)
    _apply_shadow_schema(shadow_path)

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


def _login(client):
    page = client.get("/auth/login")
    token = _extract_csrf(page.get_data(as_text=True))
    client.post(
        "/auth/login",
        data={"password": os.environ["APP_PASSWORD"], "csrf_token": token},
    )


def _seed_shadow_events(app):
    from app.db import get_db
    from app.event_models import append_event

    events = [
        ("2026-06-15 18:00:00", "system.heartbeat", {"station_id": "S1"}),
        ("2026-06-15 19:00:00", "telemetry.financial.bid", {"lot_id": "L1", "amount_cents": 5000}),
    ]
    with app.app_context():
        with get_db(immediate=True) as conn:
            for logical_ts, event_type, payload in events:
                append_event(conn, uuid.uuid4().hex, logical_ts, event_type, _canon(payload), "test")


def test_ro_connection_rejects_writes(env_dbs):
    """WHEN any write is attempted on the open_live_ro connection
    THE SYSTEM SHALL raise sqlite3.OperationalError."""
    from app.db import open_live_ro

    ro_conn = open_live_ro(env_dbs["live"])
    try:
        with pytest.raises(sqlite3.OperationalError):
            ro_conn.execute(
                "INSERT INTO source_events (seq, idempotency_key, logical_ts, event_type, payload, source)"
                " VALUES (99, 'x', '2026-06-15 21:00:00', 'system.heartbeat', '{}', 'x')"
            )
    finally:
        ro_conn.close()


def test_ro_connection_can_read(env_dbs):
    """The read-only connection must still be able to read the live corpus."""
    from app.db import open_live_ro

    ro_conn = open_live_ro(env_dbs["live"])
    try:
        rows = ro_conn.execute("SELECT COUNT(*) AS n FROM source_events").fetchone()
        assert rows["n"] == 2
    finally:
        ro_conn.close()


def test_live_content_hash_stable(env_dbs):
    """live_content_hash is deterministic for an unchanged live DB."""
    from app.db import open_live_ro
    from app.live_guard import live_content_hash

    c1 = open_live_ro(env_dbs["live"])
    c2 = open_live_ro(env_dbs["live"])
    try:
        h1 = live_content_hash(c1)
        h2 = live_content_hash(c2)
    finally:
        c1.close()
        c2.close()
    assert h1 == h2
    assert isinstance(h1, str) and len(h1) > 0


def test_replay_leaves_live_unchanged(app, client):
    """WHEN a replay completes THE SYSTEM SHALL record live_hash_pre == live_hash_post."""
    _seed_shadow_events(app)

    _login(client)
    page = client.get("/auth/login")
    token = _extract_csrf(page.get_data(as_text=True))
    resp = client.post("/replay/run", headers={"X-CSRFToken": token})
    assert resp.status_code in (200, 302)

    with app.app_context():
        from app.db import get_db

        with get_db() as conn:
            row = conn.execute(
                "SELECT status, live_hash_pre, live_hash_post FROM replay_runs"
                " WHERE status='COMPLETE_PASS' ORDER BY rowid DESC LIMIT 1"
            ).fetchone()

    assert row is not None
    assert row["live_hash_pre"] is not None
    assert row["live_hash_post"] is not None
    # Shadow isolation invariant (frozen #3): live is byte-identical pre/post replay.
    assert row["live_hash_pre"] == row["live_hash_post"]
