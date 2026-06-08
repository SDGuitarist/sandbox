"""Route smoke test for the CPAA event-replay simulator.

Hits every route in the plan's §14 route smoke table using tempfile DBs
(NEVER :memory: — FC49), real secrets set via os.environ.setdefault() below,
and the real CSRF token extracted from the rendered login form.

Run with:  cpaa-replay/.venv/bin/python smoke_test.py
"""

import os
import sqlite3
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SHADOW_SCHEMA = os.path.join(_HERE, "schema", "shadow_schema.sql")
_LIVE_SCHEMA = os.path.join(_HERE, "schema", "live_schema.sql")

# Secrets / config set INSIDE the file (FC8). setdefault so a real env wins.
os.environ.setdefault("SECRET_KEY", "smoke-secret-key")
os.environ.setdefault("APP_PASSWORD", "smoke-password")

_PASSWORD = os.environ["APP_PASSWORD"]

_PASSED = []
_FAILED = []


def _check(name, condition, detail=""):
    if condition:
        _PASSED.append(name)
        print(f"PASS  {name}")
    else:
        _FAILED.append((name, detail))
        print(f"FAIL  {name}  {detail}")


def _build_dbs():
    live_fd, live_path = tempfile.mkstemp(suffix="_smoke_live.db")
    shadow_fd, shadow_path = tempfile.mkstemp(suffix="_smoke_shadow.db")
    os.close(live_fd)
    os.close(shadow_fd)

    live = sqlite3.connect(live_path)
    with open(_LIVE_SCHEMA, "r", encoding="utf-8") as fh:
        live.executescript(fh.read())
    live.execute(
        "INSERT INTO source_events (seq, idempotency_key, logical_ts, event_type, payload, source)"
        " VALUES (1, 'sk1', '2026-06-15 18:00:00', 'system.heartbeat',"
        " '{\"station_id\":\"S1\"}', 'live')"
    )
    live.commit()
    live.execute("PRAGMA journal_mode=DELETE")
    live.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    live.close()

    shadow = sqlite3.connect(shadow_path)
    shadow.execute("PRAGMA journal_mode=WAL")
    shadow.execute("PRAGMA foreign_keys=ON")
    with open(_SHADOW_SCHEMA, "r", encoding="utf-8") as fh:
        shadow.executescript(fh.read())
    shadow.close()

    os.environ["LIVE_DB"] = live_path
    os.environ["SHADOW_DB"] = shadow_path
    return live_path, shadow_path


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


def _csrf_from_login(client):
    page = client.get("/auth/login")
    return _extract_csrf(page.get_data(as_text=True))


def main():
    live_path, shadow_path = _build_dbs()
    try:
        from app import create_app

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        # --- Public read routes ---
        _check("GET / -> 200", client.get("/").status_code == 200)
        _check("GET /runs -> 200", client.get("/runs").status_code == 200)

        # --- Auth: bad password -> 401 ---
        token = _csrf_from_login(client)
        bad = client.post(
            "/auth/login",
            data={"password": "wrong-password", "csrf_token": token},
        )
        _check("POST /auth/login (bad password) -> 401", bad.status_code == 401,
               f"got {bad.status_code}")

        # --- Auth: good password -> 302 (sets session) ---
        token = _csrf_from_login(client)
        good = client.post(
            "/auth/login",
            data={"password": _PASSWORD, "csrf_token": token},
        )
        _check("POST /auth/login (valid) -> 302", good.status_code == 302,
               f"got {good.status_code}")

        # --- Ingest: login + X-CSRFToken ---
        token = _csrf_from_login(client)
        ingest = client.post("/ingest/run", headers={"X-CSRFToken": token})
        _check("POST /ingest/run -> 200/302/409",
               ingest.status_code in (200, 302, 409),
               f"got {ingest.status_code}")

        # --- Replay: login + X-CSRFToken ---
        token = _csrf_from_login(client)
        replay = client.post("/replay/run", headers={"X-CSRFToken": token})
        _check("POST /replay/run -> 200/302/409",
               replay.status_code in (200, 302, 409),
               f"got {replay.status_code}")

        # --- Point-in-time projection: valid t ---
        pit_ok = client.get("/replay/projection/at?t=2026-06-15 19:00:00")
        _check("GET /replay/projection/at?t=<valid> -> 200",
               pit_ok.status_code == 200, f"got {pit_ok.status_code}")

        # --- Point-in-time projection: malformed t -> 400 ---
        pit_bad = client.get("/replay/projection/at?t=bad")
        _check("GET /replay/projection/at?t=bad -> 400",
               pit_bad.status_code == 400, f"got {pit_bad.status_code}")

        # --- Run detail: known run_id (read it from shadow.db) -> 200 ---
        known_run_id = _first_run_id(shadow_path)
        if known_run_id:
            rd = client.get(f"/replay/run/{known_run_id}")
            _check("GET /replay/run/<known> -> 200", rd.status_code == 200,
                   f"got {rd.status_code} for {known_run_id}")
        else:
            _check("GET /replay/run/<known> -> 200", False,
                   "no run row created to test against")

        # --- Run detail: nonexistent (8 hex chars) -> 404 ---
        missing = client.get("/replay/run/zzzzzzzz")
        _check("GET /replay/run/zzzzzzzz -> 404", missing.status_code == 404,
               f"got {missing.status_code}")

        # --- Validate run: JSON body, X-CSRFToken ---
        token = _csrf_from_login(client)
        val = client.post(
            "/validate/run",
            json={"run_a": "aaaaaaaa", "run_b": "bbbbbbbb"},
            headers={"X-CSRFToken": token},
        )
        _check("POST /validate/run -> 200/202/400/404/409",
               val.status_code in (200, 202, 400, 404, 409),
               f"got {val.status_code}")

        # --- Validate detail: nonexistent result_id -> 404 ---
        vd = client.get("/validate/999999")
        _check("GET /validate/999999 -> 404", vd.status_code == 404,
               f"got {vd.status_code}")

    finally:
        for p in (live_path, shadow_path):
            try:
                os.unlink(p)
            except OSError:
                pass

    print()
    print(f"SMOKE SUMMARY: {len(_PASSED)} passed, {len(_FAILED)} failed")
    if _FAILED:
        for name, detail in _FAILED:
            print(f"  FAILED: {name}  {detail}")
        return 1
    return 0


def _first_run_id(shadow_path):
    conn = sqlite3.connect(shadow_path)
    try:
        row = conn.execute(
            "SELECT run_id FROM replay_runs ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
