# HANDOFF -- Sandbox Eval Harness

**Date:** 2026-06-01
**Branch:** `feat/pitfall-eval-harness`
**Phase:** Compound complete. Solution doc written, learnings propagated.

## Current State

The spec eval gate (step 9w.8) is complete through the compound phase. It fills the gap between structural completeness (9w.6) and actual swarm execution (10w) by testing whether agents can follow a spec's concrete instructions. Pipeline validated end-to-end on WRC spec: 130 claims, 81% HIGH pass rate, $0.90, ~6.5 min. 3 P1s fixed in review. 8 P2s + 8 P3s deferred.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | `eval-harness/docs/brainstorms/2026-05-24-spec-eval-gate-brainstorm.md` |
| Plan | `eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md` |
| Review | 7-agent review, P1s fixed in commit `b4270fa` |
| Solution | `docs/solutions/2026-06-01-spec-eval-gate-pre-swarm-validation.md` |
| Calibration | `eval-harness/calibration/spec-eval/` (WRC + Ethics Toolkit extraction artifacts) |

## Deferred Review Findings

### P2 (should fix, next session)

- `evidence == "error"` stringly-typed sentinel -- use `failure_type` field instead
- Missing type annotations (`scenario` param, `list[tuple]`)
- Silent error on missing judge prompt -- should raise at startup
- Bare `python3` in SKILL.md -- may pick wrong interpreter
- Dead code: `ScoringError` class, unused imports
- Semaphore=5 too conservative -- make configurable, default 10
- Single 600s timeout -- extraction needs 600s, scenarios need 60s

### P3 (nice-to-have)

- Prompt injection hardening (XML tags in runner/judge)
- Remove redundant blocklist in `_is_code_testable_table`
- Remove unused CostTracker token fields (already cleaned by P1 fix)
- Remove never-populated `ClaimResult.failure_type`/`fix_hint`
- Cache judge prompt at module level
- `os.path` vs `pathlib` inconsistency
- `GateConfig` as dataclass vs Pydantic

## Concurrent Work

Branch `refactor/autopilot-agent-delegation` (worktree: `~/Projects/sandbox-autopilot-delegation`) modifies SKILL.md solo-path + Shared Tail. Swarm-path steps preserved. No conflict with 9w.8. See `docs/handoffs/2026-05-25-cross-plan-dependency-autopilot.md`.

## Three Questions

1. **Hardest decision?** Table filter design -- allowlist-by-header with conservative default-skip. Validated by 81% pass rate with 24 genuine failures vs 62% without filtering.
2. **What was rejected?** No filter (62%, $3, 86 false failures). Section-name filter (fragile). LLM classification (adds cost). Percentage threshold >= 80% (waters down gate).
3. **Least confident about?** Whether the 24 WRC failures include false positives from the anti-leniency judge. First real swarm run using this gate will calibrate.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is the eval harness in sandbox.
Spec eval gate is compound-complete. Next: address P2 deferred
findings (stringly-typed sentinel, type annotations, configurable
semaphore, split timeouts). Key files: eval-harness/spec_eval_gate.py,
eval-harness/extractor.py, eval-harness/spec_scorer.py.
```
