STATUS: FAIL noted (non-blocking — pre-diagnosed P1 defect)

# Smoke Test — Run 069

Run command: `PYTHONPATH=cpaa-replay python cpaa-replay/smoke_test.py`

## Result

Smoke test could not complete. `create_app()` raised `ImportError` at blueprint
registration — the same pre-diagnosed P1 defect from known-integration-defects.md:

```
app/ingest_routes.py:9: in <module>
    from app.ingest import ingest
ImportError: cannot import name 'ingest' from 'app.ingest'
```

All smoke routes were **unreachable** because the Flask app failed to start.

## Root Cause

DEFECT 1 (P1) from `docs/reports/069/known-integration-defects.md`:
- B3 `ingest_routes.py` imports `ingest` (does not exist)
- B2 `ingest.py` exports `ingest_source`
- Fix: change import + call in `ingest_routes.py` (one-line fix at route layer)

## Impact

This single P1 import error cascades to all routes (not just ingest). The app
cannot be instantiated until this is fixed in resolve-todos.

DEFECT 2 (P1) — C6 `replay_routes.py` calls `run_replay(conn)` but C1 defines
`run_replay()` with no args — would surface as TypeError on `POST /replay/run`
if the app started. Also pre-diagnosed, also fix target for resolve-todos.

DEFECT 3 (P3) — `GOLDEN_PROJECTION_HASH` absent from constants.py until
`tools/compute_golden.py` runs. F1 golden test gracefully skips (1 skip observed).

## Non-Blocking Classification

Per CLAUDE.md escalation rules and assembly instructions: smoke/test failures
are non-blocking. The P1s are pre-diagnosed, documented, and slated for
resolve-todos. Assembly continues.

## Retry

Not attempted — the defect is a pre-diagnosed structural wiring issue, not a
transient failure. A retry would produce the same result.
