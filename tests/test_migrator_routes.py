"""Integration tests for Flask migration runner API routes."""
import pytest

from migrator.app import create_app
from migrator.db import acquire_lock, get_db, init_db


def write_migration(migrations_dir, filename, content):
    f = migrations_dir / filename
    f.write_text(content)
    return f


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    app = create_app(db_path=db_path, migrations_dir=str(migrations_dir))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, db_path, migrations_dir


# ── GET /migrate/status ───────────────────────────────────────────────────────

def test_status_empty(client):
    c, _, _ = client
    resp = c.get("/migrate/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"applied": [], "pending": [], "missing": []}


def test_status_with_migrations(client):
    c, _, md = client
    write_migration(md, "0001_a.sql",
        "-- migrate:up\nCREATE TABLE a (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE a;")
    resp = c.get("/migrate/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["pending"]) == 1
    assert data["pending"][0]["version"] == "0001"


# ── POST /migrate/up ──────────────────────────────────────────────────────────

def test_up_applies_migrations(client):
    c, _, md = client
    write_migration(md, "0001_t.sql",
        "-- migrate:up\nCREATE TABLE t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t;")
    resp = c.post("/migrate/up", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["applied"] == ["0001"]
    assert data["dry_run"] is False


def test_up_idempotent(client):
    c, _, md = client
    write_migration(md, "0001_t.sql",
        "-- migrate:up\nCREATE TABLE t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t;")
    c.post("/migrate/up", json={})
    resp = c.post("/migrate/up", json={})
    assert resp.status_code == 200
    assert resp.get_json()["applied"] == []


def test_up_dry_run(client):
    c, db_path, md = client
    write_migration(md, "0001_t.sql",
        "-- migrate:up\nCREATE TABLE dry_t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE dry_t;")
    resp = c.post("/migrate/up", json={"dry_run": True})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["dry_run"] is True
    assert data["applied"] == ["0001"]
    # Table must not exist
    import sqlite3
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT name FROM sqlite_master WHERE name='dry_t'").fetchone()
    conn.close()
    assert row is None


def test_up_with_target(client):
    c, _, md = client
    write_migration(md, "0001_a.sql",
        "-- migrate:up\nCREATE TABLE a (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE a;")
    write_migration(md, "0002_b.sql",
        "-- migrate:up\nCREATE TABLE b (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE b;")
    write_migration(md, "0003_c.sql",
        "-- migrate:up\nCREATE TABLE c (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE c;")
    resp = c.post("/migrate/up", json={"target": "0002"})
    assert resp.status_code == 200
    assert resp.get_json()["applied"] == ["0001", "0002"]
    # 0003 still pending
    status = c.get("/migrate/status").get_json()
    assert any(p["version"] == "0003" for p in status["pending"])


def test_up_lock_contention_409(client):
    c, db_path, md = client
    write_migration(md, "0001_t.sql",
        "-- migrate:up\nCREATE TABLE t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t;")
    init_db(db_path)
    with get_db(path=db_path, immediate=True) as conn:
        acquire_lock(conn, "other")
    resp = c.post("/migrate/up", json={})
    assert resp.status_code == 409
    assert "lock" in resp.get_json()["error"].lower()


def test_up_invalid_target_400(client):
    c, _, _ = client
    resp = c.post("/migrate/up", json={"target": 123})
    assert resp.status_code == 400


# ── POST /migrate/down ────────────────────────────────────────────────────────

def test_down_rolls_back(client):
    c, _, md = client
    write_migration(md, "0001_t.sql",
        "-- migrate:up\nCREATE TABLE t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t;")
    c.post("/migrate/up", json={})
    resp = c.post("/migrate/down", json={})
    assert resp.status_code == 200
    assert resp.get_json()["rolled_back"] == ["0001"]


def test_down_steps(client):
    c, _, md = client
    write_migration(md, "0001_a.sql",
        "-- migrate:up\nCREATE TABLE a (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE a;")
    write_migration(md, "0002_b.sql",
        "-- migrate:up\nCREATE TABLE b (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE b;")
    c.post("/migrate/up", json={})
    resp = c.post("/migrate/down", json={"steps": 2})
    assert resp.status_code == 200
    assert resp.get_json()["rolled_back"] == ["0002", "0001"]


def test_down_no_down_sql_409(client):
    c, _, md = client
    write_migration(md, "0001_nodown.sql", "-- migrate:up\nCREATE TABLE nd (id INTEGER PRIMARY KEY);")
    c.post("/migrate/up", json={})
    resp = c.post("/migrate/down", json={})
    assert resp.status_code == 409
    assert "no down SQL" in resp.get_json()["error"]


def test_down_dry_run(client):
    c, db_path, md = client
    write_migration(md, "0001_t.sql",
        "-- migrate:up\nCREATE TABLE t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t;")
    c.post("/migrate/up", json={})
    resp = c.post("/migrate/down", json={"dry_run": True})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["dry_run"] is True
    assert data["rolled_back"] == ["0001"]
    # Table still exists
    import sqlite3
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT name FROM sqlite_master WHERE name='t'").fetchone()
    conn.close()
    assert row is not None


def test_down_invalid_steps_400(client):
    c, _, _ = client
    resp = c.post("/migrate/down", json={"steps": 0})
    assert resp.status_code == 400


def test_down_no_applied_returns_empty(client):
    c, _, _ = client
    resp = c.post("/migrate/down", json={})
    assert resp.status_code == 200
    assert resp.get_json()["rolled_back"] == []


# ── DELETE /migrate/lock ──────────────────────────────────────────────────────

def test_force_release_lock(client):
    c, db_path, md = client
    init_db(db_path)
    with get_db(path=db_path, immediate=True) as conn:
        acquire_lock(conn, "crashed-process")
    resp = c.delete("/migrate/lock")
    assert resp.status_code == 200
    assert resp.get_json()["released"] is True
    # Now up should work
    write_migration(md, "0001_t.sql",
        "-- migrate:up\nCREATE TABLE t (id INTEGER PRIMARY KEY);\n-- migrate:down\nDROP TABLE t;")
    resp = c.post("/migrate/up", json={})
    assert resp.status_code == 200
