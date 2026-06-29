# FINDING (HIGH) — Firebreak deadlocks the unattended tail + teardown (G1 live, secondary)

**Run:** 079 · **Discovered:** Step 17w (after G1 PASS, after swarm assembly PASS)
**Severity:** HIGH (blocks unattended completion) · **Status of G1 primary goal:** ALREADY PROVEN (probe PASS)

## What happened
With the firebreak ACTIVE, three orchestrator/tail python invocations were DEFERRED
as `indirection`:
1. `python3 tools/verify_delegated_status.py ...` (Steps 11w–16w disk-verify) → deferred.
2. `python3 .claude/hooks/firebreak-activate.py set-phase tail` (Step 17w) → deferred.
3. (by the same mechanism) `python3 .claude/hooks/firebreak-activate.py deactivate`
   (Step 18w teardown) and the tail-runner's python-based gates (verify-self-audit /
   **Gate 8 = G3**) would also be deferred.

## Root cause (classifier code, `.claude/hooks/firebreak-classify.py`)
- `classify_simple_command` calls `bash_indirection(words, cmd, sentinel)` (line ~2070)
  for **every identity**. `bash_indirection` defers any interpreter/script
  (`python`, `./x.sh`, `/abs/script`, `.venv/bin/...`) UNLESS it structurally matches
  `KNOWN_TEST_FRAMEWORKS` (pytest only).
- There is **NO trusted-identity bypass** of the indirection check (TRUSTED only
  bypasses worker-specific control-plane heuristics, lines 1987/1994, and gets
  control-plane *Write* allowance, line 2122). Indirection is identity-agnostic.
- There is **NO phase relaxation**: `classify()` never reads sentinel `phase`; flipping
  to `phase=tail` would NOT re-enable python. (And set-phase itself is deferred, so the
  flip can't even be performed via the documented command.)

## Why the bench missed it (harness-green ≠ live)
The 265/265 classifier tests validate the *classification logic* on synthetic tool
inputs. They never exercised the **full live lifecycle** where the orchestrator and the
trusted tail-runner must themselves run python (disk-verify gates, firebreak teardown,
Gate-8 verification) WHILE the firebreak they activated is governing the same repo.
This is the exact "a silently-inert gate passes every bench test" inverse: here a
*correctly-firing* gate is **too broad** and strangles the pipeline that owns it.

## Contradiction in the wiring
- autopilot Step 18w tears down via `python3 .claude/hooks/firebreak-activate.py deactivate`
  (Bash) — **deferred** by the firebreak. So the documented teardown cannot run unattended.
- But the classifier explicitly ALLOWS the trusted orchestrator to **Write** the sentinel
  (lines 2118–2123, incl. the blanket-mode "sentinel teardown" carve-out). → the INTENDED
  teardown path is an orchestrator **Write-tool** sentinel edit, which the skill does not use.
- Likewise the orchestrator's 11w–16w/18w disk-verifies and the tail's Gate-8 python need
  either (a) an indirection allowlist for trusted-orchestrator/tail pipeline tools
  (`tools/verify_delegated_status.py`, `tools/check_spec_provenance.py`,
  `.claude/hooks/firebreak-activate.py`, verify-self-audit gate scripts), or
  (b) a trusted-identity bypass of `bash_indirection`.

## Proposed fixes (for the G1 backlog — do NOT implement in this validation run)
1. **Trusted-tool indirection allowlist:** in `bash_indirection` (or `classify_simple_command`),
   allow a small hardcoded set of repo pipeline tools when `identity in TRUSTED`
   (orchestrator/tail-runner): `firebreak-activate.py`, `tools/verify_delegated_status.py`,
   `tools/check_spec_provenance.py`, and the verify-self-audit gate runner. Keep workers fully
   governed.
2. **Teardown via Write tool:** change autopilot Step 18w / 17w to deactivate/flip the
   sentinel via the Write/Edit tool (trusted control-plane write, already allowed) instead of a
   Bash python call.
3. Add a live-lifecycle integration test (orchestrator+tail python under an active sentinel),
   not just classifier-unit tests, so this class is caught on the bench next time.

## REFINEMENT (post-teardown, 2026-06-29) — recoverable, not an unrecoverable deadlock
Empirically tested at teardown:
- `rm .claude/firebreak-active.json` from the TRUSTED orchestrator → **ALLOWED** (exit 0).
  The control-plane DELETE check exempts TRUSTED identities (only *workers* are denied
  control-plane deletes), and `rm` is not an interpreter so the indirection check never
  fires. So the orchestrator CAN tear the firebreak down with a single non-python bash
  command. Firebreak confirmed INACTIVE afterward; python immediately works again.
- Therefore the precise finding is NOT "the firebreak cannot be torn down." It is:
  **the DOCUMENTED python-based control path is deferred** —
  (a) `python3 .claude/hooks/firebreak-activate.py {set-phase,deactivate}` (lifecycle), and
  (b) `python3 tools/verify_delegated_status.py` / `tools/check_spec_provenance.py`
  (orchestrator disk-verify gates). (a) has a working non-python fallback (`rm` the sentinel
  / Write the sentinel for set-phase-like edits); (b) has **no non-python equivalent**, so the
  11w–16w / 18w disk-verifies must be done MANUALLY under an active firebreak (as was done
  this run) until the classifier allowlists them.

## Scope precision (do NOT overclaim — per operator note)
The blocker is **Bash-invoked python**, i.e. the orchestrator's pipeline tooling and the
firebreak's own lifecycle commands. It is NOT a claim that Gate 8 / G3 logic "cannot run under
a firebreak":
- `verify-self-audit`'s gates are largely Read/Grep/Glob; the disconfirmer + self-audit agents
  Write to `docs/reports/` (inside-worktree, NOT control-plane) → those are ALLOWED by the
  classifier and are not themselves firebreak-blocked.
- Only any Bash-`python` step a tail component shells out to would be deferred. The correct fix
  targets the python tooling + teardown surface, not Gate-8 logic.

## Impact on this run
- **G1 PRIMARY GOAL: PASS** — proven before this finding (probe denied real worker
  control-plane writes; firebreak is live, not inert). This finding does NOT weaken G1; it is
  a *consequence* of G1 firing correctly.
- **G3 live happy-path:** blocked from running WITH the firebreak active. To validate G3 in the
  live tail, the firebreak must be torn down first (which is what Step 18w does anyway — just
  unreachable via the documented python command). Deactivating-then-tail still exercises the
  real disconfirmer→self-audit→Gate-8 chain in a live autopilot tail.
