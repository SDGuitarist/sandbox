STATUS: PASS

# Contract Check — Run 069

Checked assembled code against plan §5 Export Names Table and §6 Cross-Boundary Wiring Table.

## Export Names (§5) — All Present

| Name | Defined In | Status |
|---|---|---|
| `create_app()` | app/__init__.py:81 | PASS |
| `get_db(immediate=False)` | app/db.py:15 | PASS |
| `open_live_ro(path)` | app/db.py:45 | PASS |
| `TS_FORMAT` | app/constants.py:3 | PASS |
| `TS_RE` | app/constants.py:4 | PASS |
| `RUN_STATES` | app/constants.py:6 | PASS |
| `ANOMALY_KINDS` | app/constants.py:8 | PASS |
| `_PROJECTION_TABLES` | app/constants.py:10 | PASS |
| `DISPATCH` | app/constants.py:17 | PASS |
| `EMPTY_PROJECTION_HASH` | app/constants.py:29 | PASS |
| `canonical_hash(conn) -> str` | app/serialization.py:64 | PASS |
| `parse_json(raw)` | app/payload.py:37 | PASS |
| `parse_patch(payload, allowed)` | app/payload.py:52 | PASS |
| `append_event(conn, ...)` | app/event_models.py:4 | PASS |
| `get_events(conn)` | app/event_models.py:40 | PASS |
| `events_at_time(conn, t)` | app/event_models.py:47 | PASS |
| `record_anomaly(conn, run_id, kind, ...)` | app/anomaly_models.py:13 | PASS |
| `start_run(conn) -> tuple[str, bool]` | app/run_models.py:7 | PASS |
| `active_run(conn) -> str|None` | app/run_models.py:21 | PASS |
| `mark_complete_pass(conn, run_id, ...)` | app/run_models.py:30 | PASS |
| `mark_aborted(conn, run_id)` | app/run_models.py:47 | PASS |
| `reap_stale_runs(conn) -> int` | app/run_models.py:55 | PASS |
| `write_snapshot(conn, run_id)` | app/snapshot_models.py:37 | PASS |
| `read_snapshot(conn, run_id) -> dict` | app/snapshot_models.py:59 | PASS |
| `apply_station(conn, row)` | app/proj_station.py:23 | PASS |
| `reset_station(conn)` | app/proj_station.py:13 | PASS |
| `apply_auction(conn, row)` | app/proj_auction.py:9 | PASS |
| `reset_auction(conn)` | app/proj_auction.py:42 | PASS |
| `apply_environmental(conn, row)` | app/proj_environmental.py:9 | PASS |
| `reset_environmental(conn)` | app/proj_environmental.py:39 | PASS |
| `apply_system(conn, row)` | app/proj_system.py:22 | PASS |
| `reset_system(conn)` | app/proj_system.py:60 | PASS |
| `build_projection_at(conn, t)` | app/replay_engine.py:150 | PASS |
| `live_content_hash(ro_conn)` | app/live_guard.py:12 | PASS |
| `record_determinism(conn, run_a, run_b, match, diffs)` | app/validation_models.py:6 | PASS |
| `login_required(view)` | app/__init__.py:45 | PASS |

## Blueprints + url_for Endpoints (§5) — All Present

| Blueprint | Name | Prefix | Routes | Status |
|---|---|---|---|---|
| ingest_bp | "ingest" | /ingest | POST /ingest/run | PASS |
| replay_bp | "replay" | /replay | POST /run, GET /projection/at, GET /run/<run_id> | PASS |
| validate_bp | "validate" | /validate | POST /run, GET /<int:result_id> | PASS |
| dashboard_bp | "dashboard" | / | GET /, GET /runs | PASS |
| auth_bp | "auth" | /auth | GET+POST /login, POST /logout | PASS |

## Cross-Boundary Wiring (§6) — Checked

All §6 import paths verified present in assembled code. Two known integration
defects flagged (pre-diagnosed in docs/reports/069/known-integration-defects.md):

1. B3 `app/ingest_routes.py` imports `from app.ingest import ingest` but B2
   exports `ingest_source` — NOT a spec §5/§6 named export (spec lists `ingest_source`
   in §6 wiring table? No — the spec §6 does not specify this cross-boundary name.
   Per the known-defects note, this is a route→orchestration entrypoint the frozen
   spec left unpinned. NOT a contract violation.

2. C6 `app/replay_routes.py` imports `run_replay` from `replay_engine` — the spec §5
   does not list `run_replay` as a named export in the Export Names Table. Per the
   instructions ("the spec deliberately did NOT pin two route→orchestration entrypoint
   names, so those are NOT contract violations"). NOT a contract violation.

## Verdict

STATUS: PASS — All §5 export names and §6 import paths that the spec explicitly
prescribes are present and correctly named. The two known integration defects are
unpinned route→orchestration names outside the contract scope and are explicitly
waived per assembly instructions.
