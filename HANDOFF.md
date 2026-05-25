# HANDOFF -- Pitfall Eval Harness + Spec Eval Gate

**Branch:** `feat/pitfall-eval-harness`
**Date:** 2026-05-25
**Last commit:** `44f4d94`

## What Exists

A three-layer pipeline for testing and optimizing agent-pitfalls.md rules:

1. **Eval Harness** (`eval-harness/pitfall_eval.py`) -- Tests whether LLM agents follow rules by running scenarios with/without rule injection. 25 FCs covered, 172 scenarios. Calibration gate at 90% agreement.

2. **Monte Carlo Simulator** (`eval-harness/mc_simulator.py`) -- Projects P(clean build) for N-agent swarms using eval harness pass rates + empirical relevance weights calibrated from 20 swarm builds (255 agent-runs).

3. **Relevance Calibrator** (`eval-harness/calibrate_relevance.py`) -- Extracts FC occurrence rates from build history to weight the MC simulator.

### Key Results

- **25 FCs scored:** All CLEAR after rule rewrites (FC10, FC14 regex, FC41 judge)
- **MC projection at 25 agents:** 100% clean with all rules injected
- **Total eval cost:** ~$4 across all runs

### Spec Eval Gate (IN PROGRESS -- Phase 1 complete)

A pre-swarm gate (step 9w.8) that tests whether agents can follow a spec's concrete instructions before launching a swarm build.

**Phase 1 DONE (commit 44f4d94):**
- `eval-harness/exceptions.py` -- `SpecEvalError` hierarchy (3 classes)
- `eval-harness/models.py` -- Added 7 new types: `CONFIDENCE_THRESHOLD`, `DeterministicCheck`, `Claim`, `ClaimResult`, `TierSummary`, `GateStatus`, `GateResult`
- `eval-harness/runner.py` -- Refactored `build_prompt()` and `run_scenario()` to accept `rule_text: str` + `fc_id: str` instead of `fc: FailureClass`. Added `OverloadedError` to except clause.
- `eval-harness/pitfall_eval.py` -- Caller updated. Existing behavior verified via `--dry-run`.

### Key Files

- `eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md` -- **THE PLAN (read this first)**
- `eval-harness/docs/brainstorms/2026-05-24-spec-eval-gate-brainstorm.md` -- Brainstorm with 6 key decisions
- `eval-harness/pitfall_eval.py` -- CLI entry point (refactored in Phase 1)
- `eval-harness/runner.py` -- Runner (refactored in Phase 1)
- `eval-harness/judge.py` -- Existing judge (`check_deterministic` will be reused by `spec_judge.py`)
- `eval-harness/models.py` -- All models (Phase 1 additions at bottom)
- `eval-harness/exceptions.py` -- New spec-eval exceptions
- `docs/handoffs/2026-05-25-cross-plan-dependency-autopilot.md` -- Cross-plan note (delegation branch doesn't conflict)

## What To Do Next

### Continue: Phase 2 -- Extractor (BLOCKING PREREQUISITE)

Read `eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md`, Phase 2.

Build `eval-harness/extractor.py` (~180 lines) with three parts:

1. **`parse_tables(spec_text)`** -- Deterministic markdown table parser. Targets Export Names, Input Validation, Authorization Matrix tables. Returns `list[Claim]` with `confidence=1.0`.

2. **`extract_prose_claims(spec_text_without_tables, client)`** -- Sonnet LLM extraction via `messages.parse()` with Pydantic. Uses the extraction prompt in the plan's "Prompt Design" section. Strip parsed tables before sending to Sonnet (20-40% cost reduction). Wrap spec in `<SPEC_DOCUMENT>` delimiters for prompt injection defense.

3. **`deduplicate_claims(claims)`** -- Source location + normalized text hash. Keep table version over prose version.

**BLOCKING PREREQUISITE:** Phase 2 is NOT complete until:
- Extraction tested against WRC spec (`docs/plans/2026-05-03-feat-writers-room-council-app-spec.md`) with `--dry-run`
- Extraction tested against Ethics Toolkit spec
- Calibration artifacts checked in to `eval-harness/calibration/spec-eval/wrc-extraction.json` and `ethics-extraction.json`
- Phase 3 does NOT start until these artifacts exist

**Critical implementation details:**
- Co-locate extraction prompt with `Claim` model in `extractor.py`
- Use `messages.parse()` with Pydantic `ExtractionResult` model for guaranteed schema
- Include `rejected_statements` field in extraction output
- Include `confidence_reasoning` per prose claim
- Confidence calibration: 0.95+ for direct quotes, 0.85-0.94 for clear requirements, reject below 0.70

### Remaining Phases (after Phase 2 prerequisite clears)

| Phase | What | Key File |
|-------|------|----------|
| 3 | Scenario generator | `spec_scenario_gen.py` -- maps Claims to Scenarios. Use `variant="with_rule"`. Scenarios stay in memory. |
| 4 | Gate scorer | `spec_scorer.py` -- confidence-filtered 100% threshold. JSON report only (no MD for v1). |
| 5 | CLI + integration | `spec_eval_gate.py` -- Click CLI, async via `asyncio.to_thread()`. `spec_judge.py` -- new judge reusing `check_deterministic`. `judges/spec-eval-base.txt`. |

### Start Command

```
cd ~/Projects/sandbox/eval-harness
Read eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md.
Implement Phase 2 (Extractor). Relevant files: eval-harness/models.py
(Claim, DeterministicCheck models), eval-harness/judge.py (check_deterministic
for reference pattern). Ground truth table for extraction validation is in
the plan's "Prompt Design" section.
```

## Concurrent Work Awareness

Branch `refactor/autopilot-agent-delegation` (worktree: `~/Projects/sandbox-autopilot-delegation`) modifies `.claude/skills/autopilot/SKILL.md` but only touches solo-path steps (3, 5, 6, 7s). Swarm-path steps (7w-16w) are preserved. Step 9w.8 goes in the swarm path -- no conflict.

## Feed-Forward

- **Hardest decision:** Refactoring `runner.py` (4+6+4 lines) vs. synthetic FailureClass hack. Reviews proved the hack would have silently failed (`variant="spec_adherence"` doesn't inject rule_text, `tier: 0` crashes Pydantic). The refactor was the right call.
- **Rejected alternatives:** (1) Synthetic FC hack (two bugs). (2) Adding `"spec_adherence"` to Variant literal (couples two independent systems). (3) Modifying judge.py (creates new `spec_judge.py` instead).
- **Least confident:** The Sonnet extraction prompt. Everything downstream (scenarios, runner, judge, scorer) is well-specified. Whether Sonnet can reliably decompose prose into testable claims at the right granularity is untested. This is why Phase 2 has a blocking prerequisite with checked-in calibration artifacts.
