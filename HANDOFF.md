# HANDOFF -- Pitfall Eval Harness

**Branch:** `feat/pitfall-eval-harness`
**Date:** 2026-05-24
**Last commit:** `c39bb6c`

## What Exists

A three-layer pipeline for testing and optimizing agent-pitfalls.md rules:

1. **Eval Harness** (`eval-harness/pitfall_eval.py`) -- Tests whether LLM agents follow rules by running scenarios with/without rule injection. 25 FCs covered, 172 scenarios. Calibration gate at 90% agreement.

2. **Monte Carlo Simulator** (`eval-harness/mc_simulator.py`) -- Projects P(clean build) for N-agent swarms using eval harness pass rates + empirical relevance weights calibrated from 20 swarm builds (255 agent-runs).

3. **Relevance Calibrator** (`eval-harness/calibrate_relevance.py`) -- Extracts FC occurrence rates from build history to weight the MC simulator.

### Key Results

- **25 FCs scored:** All CLEAR after rule rewrites (FC10, FC14 regex, FC41 judge)
- **14 load-bearing rules** (must inject): FC24, FC35, FC39, FC47, FC17, FC20, FC23, FC16, FC25, FC4, FC9, FC19, FC36, FC10
- **11 redundant rules** (agent already knows): FC1, FC2, FC7, FC14, FC15, FC26, FC27, FC28, FC33, FC46, FC41
- **MC projection at 25 agents:** 100% clean with all rules injected (up from 60.5% before FC10 fix)
- **FC10 rule rewrite:** Added "every except block MUST end with return jsonify(...), 503" -- moved 83% to 100%
- **Total eval cost:** ~$4 across all runs

### Key Files

- `eval-harness/pitfall_eval.py` -- CLI: `--stage`, `--fc`, `--calibrate`, `--dry-run`
- `eval-harness/judge.py` -- Deterministic + LLM judge (Sonnet 4.6)
- `eval-harness/mc_simulator.py` -- Monte Carlo build failure predictor
- `eval-harness/calibrate_relevance.py` -- Empirical weight computation
- `eval-harness/scenarios/` -- 25 scenario YAML files (Stage 1 + Stage 2)
- `eval-harness/judges/` -- 17 per-FC judge prompts
- `eval-harness/calibration/` -- calibration-set.yaml + relevance-weights.json
- `eval-harness/reports/` -- 5 run reports (JSONL + JSON + MD)
- `~/.claude/docs/agent-pitfalls.md` -- Source of truth (FC10 rule updated)

## What To Do Next

### Next Session: Brainstorm Spec Eval Gate (Option B -- full compound cycle)

**Goal:** Automatic pre-swarm gate that tests spec instructions before launching agents.

**The brainstorm should explore:**

1. **Scenario generation from specs.** How does an LLM read a spec and produce good scenario YAML? What makes a "testable instruction" vs untestable prose? What's the minimum spec structure needed for automatic extraction?

2. **Quality of auto-generated scenarios.** Hand-written scenarios took domain knowledge (knowing what Haiku gets wrong). Can Sonnet generate scenarios that actually catch failures, or will they be trivially easy? How do you validate scenario quality?

3. **Gate thresholds.** 80% P(clean build) as pass threshold? Should it vary by swarm size? What happens when the gate fails -- does the orchestrator auto-rewrite the spec instruction, or does it abort?

4. **Integration point.** New autopilot step 9w.7 between spec-completeness-checker and swarm-planner. What inputs/outputs? How does it interact with the existing gates?

5. **Cost and speed constraints.** Must stay under $1 and 5 minutes or it'll get skipped. How many spec instructions can you test in that budget?

**Start with:** `/workflows:brainstorm` targeting `docs/brainstorms/2026-0X-XX-spec-eval-gate-brainstorm.md`

### Later: Validate MC Against Real Builds

Run the next 3-5 swarm builds normally, record actual P1 counts, compare against MC predictions. If MC predicts 100% clean and builds still have P1s, the model needs a "noise floor" parameter for real-world context pressure.

## Feed-Forward

- **Hardest decision:** Whether to calibrate relevance from build-level occurrence (conservative) or per-agent occurrence (aggressive). Chose build-level * 0.8 as a compromise.
- **Rejected alternatives:** Guessed relevance weights (2-5x too high, made predictions useless). Per-agent calculation (denominator too large, washed out signal).
- **Least confident:** The 100% MC projection assumes all with_rule pass rates are truly 100%. Small sample sizes (6 runs per FC) mean the true rate could be 85-95%. The "noise floor" from real-world context pressure is unmodeled.
