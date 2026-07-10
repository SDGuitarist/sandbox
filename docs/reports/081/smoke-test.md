STATUS: FIREBREAK_DEFERRED

# Smoke Test — Run 081

## Result

FIREBREAK_DEFERRED: The run-081 firebreak is ACTIVE (phase=build). The smoke test invocation
(`python3 test_smoke.py`) was deferred by the G1 firebreak as a non-trusted Python invocation.

This is EXPECTED and NON-BLOCKING per the FIREBREAK NOTE in the assembly parameters:
> "if the smoke/test run is FIREBREAK_DEFERRED, record exactly that status in
> assembly-summary.md (expected, non-blocking; post-teardown re-run happens later)
> and do NOT retry or work around it."

Post-teardown re-run will execute the smoke suite after firebreak deactivation.
The `test_smoke.py` file is present in the assembled codebase (cherry-picked from
worker worktree-agent-a1dc529224391f29e, commit 4a9bc04).

## Contract Priority Flags (F5)

F5 (informational): `practice/new` will return 403 for users without a `students` row.
This is spec-correct. Tests are not weakened.
