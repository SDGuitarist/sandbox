# Fixture F-B2 — Wholly-Omitted Orchestration Entrypoint (FC50 false-N/A blind spot)

NEGATIVE-CONTROL fixture documenting a KNOWN, honest blind spot of Check 1b. The
spec contains a genuine route→engine call (`compute_schedule`) that SHOULD have
been declared as an `orchestration entrypoint` row — but the planner OMITTED that
row entirely. Check 1b is a signature-PRESENCE guard, not a call-site classifier
(spec-completeness-checker.md:88-90): it validates what the author DECLARED, so a
wholly-omitted entrypoint produces N/A, NOT FAIL.

The fixture asserts the gate returns **N/A** for the FC50 / Orchestration
Entrypoints surface — an honest "I can't see this" — never a false PASS that would
imply the entrypoint was checked. The downstream backstop for a wholly-omitted
entrypoint is the assembly contract-check (agent-prose in swarm-runner /
spec-contract-checker), which is NOT exercised here, so that backstop claim is
PROSE-ASSERTED, not EXERCISED.

## Genuine route→engine call (NOT declared as an orchestration entrypoint)

```python
# schedule/routes.py
from engine.scheduler import compute_schedule

@schedule_bp.route("/schedule/run", methods=["POST"])
def run_schedule():
    # cross-boundary call — SHOULD be an `orchestration entrypoint` row, but isn't
    return compute_schedule(project_id, lock=True)
```

There is deliberately no Export Names table and no row with
`Type = orchestration entrypoint`. Check 1b therefore enumerates zero entrypoint
rows and returns N/A — the documented blind spot. A wholly-omitted entrypoint is
invisible to this presence guard; only the downstream assembly contract-check
catches it. Expected: the FC50 surface is `N/A`, never a false PASS.
