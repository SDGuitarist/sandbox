# Fixture: Pinned Orchestration Entrypoints (FC50 — expect PASS)

Purpose: a minimal shared interface spec that declares both an orchestration
entrypoint classes (a route→non-model function call AND a tool→constants import)
crossing an agent boundary, EACH with a populated `Full Signature` cell. The
9w.6 completeness gate's Check 1b (orchestration entrypoint signature presence
guard) MUST PASS on this fixture.

This is the positive counterpart to `unpinned-entrypoint-spec.md`. It stands in
for "a plan that pins every route→non-model and tool→constants entrypoint with a
Full Signature" — the frozen Run 069 plan is NOT mutated for this proof (it
predates the row-class and honestly returns N/A).

Expected checker result: **Orchestration Entrypoints (FC50): PASS** (2 entrypoint
rows, 0 missing Full Signature).

## Export Names Table

| Name | Type | Defined By | Used By | Full Signature |
|------|------|------------|---------|----------------|
| `create_item` | model function | `app/models.py` | `items` agent | — |
| `replay_run` | orchestration entrypoint | `app/services/replay.py` | `replay` route (`app/blueprints/replay/routes.py`) | `replay_run(run_id: int, *, dedup: bool = True) -> ReplayResult` |
| `GOLDEN_PROJECTION_HASH` | orchestration entrypoint | `app/constants.py` | `projection` tool import (`tools/compute_golden.py`) | `GOLDEN_PROJECTION_HASH: str` (tool→constants import) |

## Cross-Boundary Wiring Table

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| `app/services/replay.py` | `app/blueprints/replay/routes.py` | `from app.services.replay import replay_run` |
| `app/constants.py` | `tools/compute_golden.py` | `from app.constants import GOLDEN_PROJECTION_HASH` |
