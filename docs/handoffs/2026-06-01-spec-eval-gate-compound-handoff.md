# Compound Phase Handoff: Spec Eval Gate

Read HANDOFF.md for full context. Branch: `feat/pitfall-eval-harness`. Last commit: `b277cf8`.

## What Was Built

A pre-swarm gate (step 9w.8) that tests whether agents can follow a spec's concrete instructions before launching a swarm. It fills the gap between "did the spec have the right sections" (completeness checker, 9w.6) and "can agents actually execute what those sections say."

**Pipeline:** extract claims from spec tables + Sonnet prose extraction -> generate scenarios -> run through Haiku agent -> judge with Sonnet (anti-leniency rubric) -> score with confidence-filtered 100% threshold -> PASS/FAIL gate.

## Key Results

- **WRC spec end-to-end:** 130 claims (55 table + 75 prose), 102/126 HIGH passed (81%), $0.90, ~6.5 min
- **24 genuine failures** caught: mock functions calling real APIs, missing route patterns, incorrect validation
- **Table filter:** reduced 156 raw table claims to 55 code-testable claims by allowlisting header patterns
- **Calibration:** WRC + Ethics Toolkit extraction artifacts checked in

## Review (7-agent)

3 P1s found and fixed (commit `b4270fa`):
1. **CostTracker race condition** — eliminated shared mutable state, aggregate costs after gather
2. **Missing verification artifact** — writes `spec-eval-verification.md` on PASS, Step 10w checks for it (prevents Run-054 gate bypass)
3. **Exit code ambiguity** — exit 2 for env errors (missing API key), distinct from exit 1 (spec FAIL)

8 P2s and 8 P3s deferred. See HANDOFF.md "Deferred Review Findings" for full list.

## Files Changed (13 new, 3 modified)

New: `extractor.py`, `spec_scenario_gen.py`, `spec_scorer.py`, `spec_judge.py`, `spec_eval_gate.py`, `exceptions.py`, `judges/spec-eval-base.txt`, 3 calibration JSONs, cross-plan handoff docs.
Modified: `runner.py` (accept `rule_text: str`), `models.py` (7 new types), `SKILL.md` (step 9w.8 + 10w precondition).

## Feed-Forward

- **Hardest decision:** Table filter — allowlist-by-header with conservative default-skip. Validated by 81% pass rate with 24 genuine failures.
- **Rejected alternatives:** No filter (62%, $3, 86 false failures), section-name filter (fragile), LLM classification (adds cost).
- **Least confident:** Whether the 24 WRC failures include false positives from the anti-leniency judge.

## Start Command

```
Read HANDOFF.md. Run /workflows:compound for the spec eval gate.
Plan: eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md.
Key files: eval-harness/spec_eval_gate.py, eval-harness/extractor.py, .claude/skills/autopilot/SKILL.md.
```
