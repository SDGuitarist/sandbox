---
status: complete
priority: p2
issue_id: "073"
tags: [code-review, firebreak, g1, testing, integration]
dependencies: [071, 072]
---

# P2 — No live-lifecycle integration test for firebreak orchestrator path

## Problem Statement

The 265-test classifier bench validates classification logic on synthetic tool inputs.
It does NOT exercise the full orchestrator lifecycle: firebreak activates → workers
governed → orchestrator runs disk-verify gates → phase flip → teardown. Run 079
demonstrated this gap — the firebreak passed 265/265 tests but deferred its own
orchestrator lifecycle commands when live.

## Findings

- **Evidence (run 079):** All 265 classifier tests passed. None exercised an
  orchestrator python call against an active sentinel file.
- **Pattern (docs/solutions/2026-06-25-g1-firebreak-activation-arc.md):**
  "harness-green ≠ live" — classifier tests validate classification logic on synthetic
  inputs, not end-to-end behavior.
- **Architecture reviewer finding (run 079 review):** P2. Fix C (live integration
  test) is non-negotiable but should be addressed after Fixes A/B are implemented.

## Proposed Solutions

### Solution A: Add lifecycle integration test to test_firebreak_classify.py

Add a test that:
1. Creates a live sentinel file (`firebreak-active.json`)
2. Calls the classifier for `identity=orchestrator` with `python3 tools/verify_delegated_status.py`
3. Expects GREEN (after Fix A from #071 is applied)
4. Calls the classifier for `identity=worker` with `python3 any_script.py`
5. Expects DEFERRED
6. Calls the classifier for `identity=orchestrator` with `rm .claude/firebreak-active.json`
7. Expects GREEN
8. Cleans up the sentinel file

**Pros:** Directly validates the critical lifecycle scenario.
**Effort:** Small (new test class, ~30 lines)
**Risk:** Low.

### Solution B: End-to-end live swarm test

Run a minimal swarm with G1 active and verify all orchestrator python calls succeed.
This is run 079's approach — expensive, not repeatable in CI.

**Pros:** Maximum fidelity.
**Cons:** Too heavyweight for CI; non-repeatable.
**Effort:** Large
**Risk:** Medium (requires full autopilot environment).

## Recommended Action

Implement Solution A. Add as a test class in test_firebreak_classify.py, guarded
by a `FIREBREAK_LIFECYCLE_TEST=1` env flag since it writes/reads a real sentinel file.

## Technical Details

- **Affected files:**
  - `.claude/hooks/test_firebreak_classify.py` — add lifecycle test class
  - `.claude/hooks/firebreak-classify.py` — expected behavior after #071 fix

## Acceptance Criteria

- [ ] Live-sentinel test: orchestrator `python3 verify_delegated_status.py` → GREEN
- [ ] Live-sentinel test: worker `python3 any_script.py` → DEFERRED
- [ ] Live-sentinel test: orchestrator `rm firebreak-active.json` → GREEN
- [ ] Test cleans up the sentinel file even on failure
- [ ] CI note: test requires sentinel write permission; document env flag

## Work Log

- 2026-06-29: Created from run 079 review. Architecture reviewer confirmed:
  Fix C is "non-negotiable and architecturally essential." Add after #071 is
  implemented. The next real feature swarm with G1+G3 active will also implicitly
  validate this scenario.
