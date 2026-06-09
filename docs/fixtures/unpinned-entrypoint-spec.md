# Fixture: Unpinned Orchestration Entrypoint (FC50 — expect FAIL)

Purpose: a minimal shared interface spec that declares an `orchestration
entrypoint` row with an EMPTY `Full Signature` cell. The 9w.6 completeness gate's
Check 1b (orchestration entrypoint signature presence guard) MUST FAIL on this
fixture, naming the symbol. A route→non-model call is NOT required for the guard
to fire — a single tool→constants import row is enough.

Expected checker result: **Orchestration Entrypoints (FC50): FAIL** (1 entrypoint
row, 1 missing Full Signature). Other surfaces may be N/A.

## Export Names Table

| Name | Type | Defined By | Used By | Full Signature |
|------|------|------------|---------|----------------|
| `GOLDEN_PROJECTION_HASH` | orchestration entrypoint | `app/constants.py` | `projection` tool import (`tools/compute_golden.py`) | |

## Cross-Boundary Wiring Table

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| `app/constants.py` | `tools/compute_golden.py` | `from app.constants import GOLDEN_PROJECTION_HASH` |
