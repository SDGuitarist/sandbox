# HANDOFF -- Pitfall Eval Harness + Spec Eval Gate

**Branch:** `feat/pitfall-eval-harness`
**Date:** 2026-05-31
**Last commit:** `210c958`

## What Exists

A three-layer pipeline for testing and optimizing agent-pitfalls.md rules:

1. **Eval Harness** (`eval-harness/pitfall_eval.py`) -- Tests whether LLM agents follow rules by running scenarios with/without rule injection. 25 FCs covered, 172 scenarios. Calibration gate at 90% agreement.

2. **Monte Carlo Simulator** (`eval-harness/mc_simulator.py`) -- Projects P(clean build) for N-agent swarms using eval harness pass rates + empirical relevance weights calibrated from 20 swarm builds (255 agent-runs).

3. **Relevance Calibrator** (`eval-harness/calibrate_relevance.py`) -- Extracts FC occurrence rates from build history to weight the MC simulator.

### Key Results

- **25 FCs scored:** All CLEAR after rule rewrites (FC10, FC14 regex, FC41 judge)
- **MC projection at 25 agents:** 100% clean with all rules injected
- **Total eval cost:** ~$4 across all runs

### Spec Eval Gate (Phases 1-5 complete, calibration pending)

A pre-swarm gate (step 9w.8) that tests whether agents can follow a spec's concrete instructions before launching a swarm build.

**Phase 1 DONE (commit 44f4d94):**
- `eval-harness/exceptions.py` -- `SpecEvalError` hierarchy (3 classes)
- `eval-harness/models.py` -- Added 7 new types: `CONFIDENCE_THRESHOLD`, `DeterministicCheck`, `Claim`, `ClaimResult`, `TierSummary`, `GateStatus`, `GateResult`
- `eval-harness/runner.py` -- Refactored `build_prompt()` and `run_scenario()` to accept `rule_text: str` + `fc_id: str` instead of `fc: FailureClass`. Added `OverloadedError` to except clause.
- `eval-harness/pitfall_eval.py` -- Caller updated. Existing behavior verified via `--dry-run`.

**Phase 2 DONE (commit a6410c1):**
- `eval-harness/extractor.py` -- Table parser (deterministic, confidence=1.0) + Sonnet prose extraction via `messages.parse()` + hash-based deduplication. 156 table claims extracted from WRC spec in dry-run validation.

**Phases 3-5 DONE (commit e45d3d3):**
- `eval-harness/spec_scenario_gen.py` -- Claims to Scenarios mapping (variant="with_rule")
- `eval-harness/spec_scorer.py` -- Confidence-filtered 100% threshold scoring (4 status paths)
- `eval-harness/spec_judge.py` -- Spec-adherence LLM judge with anti-leniency rubric
- `eval-harness/spec_eval_gate.py` -- Async CLI with semaphore concurrency, cost tracking, dry-run
- `eval-harness/judges/spec-eval-base.txt` -- Judge prompt (chain-of-thought before verdict)

**Calibration (commit 210c958):**
- `eval-harness/calibration/spec-eval/wrc-extraction-tables-only.json` -- 156 table claims from WRC spec (31 deterministic, 125 LLM-judge)

### Key Files

- `eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md` -- **THE PLAN**
- `eval-harness/spec_eval_gate.py` -- CLI entry point (async, Click)
- `eval-harness/extractor.py` -- Claim extraction (tables + prose)
- `eval-harness/spec_scenario_gen.py` -- Claim to Scenario mapping
- `eval-harness/spec_scorer.py` -- Gate scoring logic
- `eval-harness/spec_judge.py` -- Spec-adherence judge
- `eval-harness/judges/spec-eval-base.txt` -- Judge prompt
- `eval-harness/runner.py` -- Runner (refactored in Phase 1)
- `eval-harness/models.py` -- All models
- `eval-harness/exceptions.py` -- Spec-eval exceptions
- `docs/handoffs/2026-05-25-cross-plan-dependency-autopilot.md` -- Cross-plan note

## What To Do Next

### Blocking: Full calibration with ANTHROPIC_API_KEY

The code is complete but the blocking prerequisite requires running with a real API key:

1. Set `ANTHROPIC_API_KEY` in environment
2. Run against WRC spec:
   ```bash
   cd ~/Projects/sandbox/eval-harness
   python3 spec_eval_gate.py ../docs/plans/2026-05-03-feat-writers-room-council-app-spec.md --dry-run --verbose --output-dir calibration/spec-eval
   ```
3. Run against Ethics Toolkit spec:
   ```bash
   python3 spec_eval_gate.py ../docs/plans/2026-04-30-ethics-toolkit-platform-spec.md --dry-run --verbose --output-dir calibration/spec-eval
   ```
4. Save calibration artifacts:
   ```bash
   cp calibration/spec-eval/spec-eval-*/extraction.json calibration/spec-eval/wrc-extraction.json
   cp calibration/spec-eval/spec-eval-*/extraction.json calibration/spec-eval/ethics-extraction.json
   ```
5. Review extraction quality against plan's ground truth table
6. Commit calibration artifacts

### After calibration: Full gate run

Run the gate end-to-end on a real spec with scenarios + judging:
```bash
python3 spec_eval_gate.py ../docs/plans/2026-05-03-feat-writers-room-council-app-spec.md --verbose --cost-cap 1.0
```

Verify: exit code 0 for a well-structured spec, exit code 1 for a vague spec.

### After validation: Add step 9w.8 to autopilot SKILL.md

Add between Steps 9w.7 and 10w in the swarm path:
```
### Step 9w.8: Spec Eval Gate (MANDATORY -- SWARM ONLY)

Run the spec eval gate against the plan:
  `python3 eval-harness/spec_eval_gate.py <plan_path> --output-dir docs/reports/<run-id>`

Check exit code:
- Exit 0 (PASS): proceed to Step 10w.
- Exit 1 (FAIL/WARN/RETRY): abort with gate report details.
```

## Concurrent Work Awareness

Branch `refactor/autopilot-agent-delegation` (worktree: `~/Projects/sandbox-autopilot-delegation`) modifies `.claude/skills/autopilot/SKILL.md` but only touches solo-path steps (3, 5, 6, 7s). Swarm-path steps (7w-16w) are preserved. Step 9w.8 goes in the swarm path -- no conflict.

## Feed-Forward

- **Hardest decision:** Refactoring `runner.py` (4+6+4 lines) vs. synthetic FailureClass hack. Reviews proved the hack would have silently failed (`variant="spec_adherence"` doesn't inject rule_text, `tier: 0` crashes Pydantic). The refactor was the right call.
- **Rejected alternatives:** (1) Synthetic FC hack (two bugs). (2) Adding `"spec_adherence"` to Variant literal (couples two independent systems). (3) Modifying judge.py (creates new `spec_judge.py` instead).
- **Least confident:** The Sonnet extraction prompt. Everything downstream (scenarios, runner, judge, scorer) is well-specified. Whether Sonnet can reliably decompose prose into testable claims at the right granularity is untested. This is why Phase 2 has a blocking prerequisite with checked-in calibration artifacts.
