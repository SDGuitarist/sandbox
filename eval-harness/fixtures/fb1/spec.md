# Fixture F-B1 — Unpinned Orchestration Entrypoint (Track B / FC50 negative test)

This is a NEGATIVE-TEST fixture spec, not a real plan. It declares ONE genuine
route→orchestration call as an `orchestration entrypoint` row whose
`Full Signature` cell is left EMPTY. The shipped `spec-completeness-checker`
Check 1b (FC50) MUST FAIL, naming the symbol `compute_schedule`. If the gate
returns PASS or N/A, Track B is unproven and the fixture FAILS.

Everything else in this spec is intentionally minimal so that Check 1b is the
ONLY failing surface (all other surfaces evaluate to N/A) — the FAIL is therefore
cleanly attributable to FC50.

## Export Names Table

| Name | Type | Defined By | Used By | Full Signature |
|------|------|------------|---------|----------------|
| compute_schedule | orchestration entrypoint | engine/scheduler.py | schedule/routes.py |  |

## Genuine route→orchestration call

```python
# schedule/routes.py  (consumer — crosses the route → engine boundary)
from engine.scheduler import compute_schedule

@schedule_bp.route("/schedule/run", methods=["POST"])
def run_schedule():
    # route hands off to the engine entrypoint; verb/arity were never pinned
    return compute_schedule(project_id, lock=True)
```

The Export Names row above leaves `Full Signature` blank, so Check 1b cannot
verify the import name or arity of `compute_schedule` before swarm spawn — exactly
the demonstrated Run 069 failure mode (a route→engine call whose name or arity
drifted because the verb was never pinned). Expected gate verdict: line-1
`STATUS: FAIL` with an Orchestration Entrypoints (FC50) finding naming
`compute_schedule`.
