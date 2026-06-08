# Run 069 — Known Cross-Cluster Integration Defects (for Review / resolve-todos)

These were detected from worker self-reports during the swarm spawn. All three are
at cross-cluster **entrypoints the frozen spec §5/§6 left unpinned** — the model-layer
names §5 pinned exhaustively came out clean across all 24 agents. This is a clean FC1/FC2
confirmation at 24-agent scale (the meta-goal finding for this run).

Severity guide: P1 = app-breaking; fix in resolve-todos before final smoke re-run.

## DEFECT 1 (P1, app-breaking at import) — B2↔B3 ingest entrypoint name+arity
- **B2-ingest** (`app/ingest.py`) exports `ingest_source(conn, live_db_path) -> dict`.
- **B3-ingest-routes** (`app/ingest_routes.py`) does `from app.ingest import ingest` and calls `ingest(conn)`.
- `ingest` does not exist → ImportError at blueprint registration → `create_app()` fails →
  the ENTIRE app fails to start (all smoke routes fail, not just ingest).
- **Fix (one site, route layer):** in `ingest_routes.py` change the import to
  `from app.ingest import ingest_source` and the call to
  `ingest_source(conn, current_app.config['LIVE_DB'])`. (B2's signature is the
  authoritative one; B2 verified it produces correct dedup counts.)

## DEFECT 2 (P1, runtime TypeError on POST /replay/run) — C1↔C6 replay entrypoint arity
- **C1-replay-engine** (`app/replay_engine.py`) defines `run_replay() -> (run_id, acquired)`
  — takes NO args; it owns its own T1/T2/T3 connections (T1 must commit independently so a
  concurrent 409 path can read the RUNNING row).
- **C6-replay-routes** (`app/replay_routes.py`) calls `run_replay(conn)` inside its own
  `get_db(immediate=True)` block.
- Name matches; arity does not → `TypeError: run_replay() takes 0 args but 1 given`, and the
  route's outer transaction would double-manage the connection.
- **Fix (one site, route layer):** in `replay_routes.py` call `run_replay()` with no args and
  remove the route's surrounding `get_db(immediate=True)` wrapper for the run path (the engine
  owns the transaction lifecycle). Map `acquired=False` → 409 with active run_id; success → 302/200.

## DEFECT 3 (P3, soft — test skip, not a failure) — golden-corpus constant name
- **A6-serialization** introduced `GOLDEN_PROJECTION_HASH`; `tools/compute_golden.py` appends
  it to `app/constants.py` AFTER assembly. **A5**'s `constants.py` ships only `EMPTY_PROJECTION_HASH`.
- **F1**'s golden-corpus test discovers any `GOLDEN*` 64-hex constant and SKIPS if absent (no error).
- **Fix:** run `tools/compute_golden.py` after assembly to freeze `EMPTY_PROJECTION_HASH` +
  `GOLDEN_PROJECTION_HASH` into `constants.py`; then F1's anchor test asserts hard. Optionally add
  `GOLDEN_PROJECTION_HASH` to §5 Export Names in a future spec rev (carry-forward, not this build).

## Carry-forward (agent-pitfalls / solution doc)
Spec §5/§6 must pin route→orchestration and tool→constants entrypoint names+signatures, not just
model-layer exports. At 24-agent scale every unpinned cross-cluster entrypoint diverged (2 of 2),
while every pinned name held (clean). Add an "Orchestration Entrypoints" row-class to the Export
Names Table requirement.
