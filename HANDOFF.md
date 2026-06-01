# HANDOFF -- Spec Eval Gate

**Date:** 2026-06-01
**Branch:** `feat/pitfall-eval-harness`
**Last commit:** `b4270fa`
**Phase:** Review complete, P1s fixed. Ready for compound.

## What Exists

### Pitfall Eval Harness (prior work)

Three-layer pipeline for testing agent-pitfalls.md rules: eval harness (25 FCs, 172 scenarios), Monte Carlo simulator (P(clean build) projections), relevance calibrator (empirical weights from 20 builds).

### Spec Eval Gate (this session -- complete)

Pre-swarm gate (step 9w.8) that tests whether agents can follow a spec's concrete instructions before launching. Fills the gap between structural completeness (9w.6) and actual agent execution (10w).

**Pipeline:** extract claims (tables + prose) -> generate scenarios -> run through Haiku -> judge with Sonnet -> score with confidence-filtered 100% threshold -> gate PASS/FAIL.

**Validated end-to-end:**
- WRC spec: 130 claims, 102/126 HIGH passed (81%), $0.90, ~6.5 min
- Ethics Toolkit: 156 claims extracted (dry-run calibration)
- Both calibration artifacts checked in

### Review (7-agent, P1s fixed)

| Agent | Key Finding |
|-------|-------------|
| Python | CostTracker race condition (P1, FIXED) |
| Security | No-code-execution invariant confirmed, prompt injection partial |
| Performance | Semaphore too conservative, separate timeouts needed |
| Architecture | Clean module boundaries, correct runner refactor |
| Simplicity | ~25 lines dead code to remove |
| Agent-Native | Missing verification artifact (P1, FIXED), exit code ambiguity (P1, FIXED) |
| Learnings | 6 solution docs applied, follows established gate patterns |

**P1s fixed (commit b4270fa):**
1. CostTracker race -- eliminated shared mutable state, aggregate after gather
2. Verification artifact -- writes spec-eval-verification.md on PASS, 10w checks for it
3. Exit code 2 for env errors -- distinct from spec FAIL, no wasted retries

## Key Files

| File | Purpose |
|------|---------|
| `eval-harness/spec_eval_gate.py` | CLI entry point (async, Click) |
| `eval-harness/extractor.py` | Claim extraction (tables + prose + dedup) |
| `eval-harness/spec_scenario_gen.py` | Claim to Scenario mapping |
| `eval-harness/spec_scorer.py` | Gate scoring (confidence-filtered 100% threshold) |
| `eval-harness/spec_judge.py` | Spec-adherence LLM judge |
| `eval-harness/judges/spec-eval-base.txt` | Judge prompt (anti-leniency rubric) |
| `eval-harness/runner.py` | Runner (refactored to accept rule_text) |
| `eval-harness/models.py` | All models (Claim, GateResult, etc.) |
| `.claude/skills/autopilot/SKILL.md` | Step 9w.8 + 10w precondition updates |
| `eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md` | The plan |
| `docs/handoffs/2026-05-25-cross-plan-dependency-autopilot.md` | Cross-plan note |

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

## Feed-Forward

- **Hardest decision:** Table filter design. Allowlist-by-header with conservative default-skip. 156->55 table claims on WRC. 81% pass rate with 24 genuine failures validates the balance.
- **Rejected alternatives:** No filter (62% pass, $3, 86 false failures). Section-name filter (fragile). LLM classification (adds cost to pre-flight gate).
- **Least confident:** Whether the 24 WRC failures are all genuine or include false positives from the anti-leniency judge. The judge biases toward FAIL, which is correct for a pre-swarm gate but may over-flag complex instructions.

## Prompt for Next Session

```
Read HANDOFF.md for context. Spec eval gate is complete through review.
P1s fixed, P2/P3 deferred. Next: /workflows:compound to write solution doc,
then address P2 findings if time permits.
```
