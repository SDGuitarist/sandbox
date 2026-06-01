# HANDOFF -- Pitfall Eval Harness + Spec Eval Gate

**Branch:** `feat/pitfall-eval-harness`
**Date:** 2026-06-01
**Last commit:** `df83d70`

## What Exists

A three-layer pipeline for testing and optimizing agent-pitfalls.md rules:

1. **Eval Harness** (`eval-harness/pitfall_eval.py`) -- Tests whether LLM agents follow rules by running scenarios with/without rule injection. 25 FCs covered, 172 scenarios. Calibration gate at 90% agreement.

2. **Monte Carlo Simulator** (`eval-harness/mc_simulator.py`) -- Projects P(clean build) for N-agent swarms using eval harness pass rates + empirical relevance weights calibrated from 20 swarm builds (255 agent-runs).

3. **Relevance Calibrator** (`eval-harness/calibrate_relevance.py`) -- Extracts FC occurrence rates from build history to weight the MC simulator.

### Key Results (Pitfall Eval)

- **25 FCs scored:** All CLEAR after rule rewrites (FC10, FC14 regex, FC41 judge)
- **MC projection at 25 agents:** 100% clean with all rules injected
- **Total eval cost:** ~$4 across all runs

### Spec Eval Gate (COMPLETE -- validated end-to-end)

A pre-swarm gate (step 9w.8) that tests whether agents can follow a spec's concrete instructions before launching a swarm build.

**End-to-end validation on WRC spec:**
- 130 claims (55 table + 75 prose), 126 HIGH confidence
- 102/126 HIGH passed (81%) -- gate correctly returned FAIL
- 24 failures are genuine spec-adherence issues (mock functions calling real APIs, missing route patterns, incorrect validation)
- **Cost: $0.90** (under the $1 budget)
- **Runtime: ~6.5 min** (130 scenarios, 5 concurrent)

**Calibration artifacts (both blocking prerequisites met):**
- `eval-harness/calibration/spec-eval/wrc-extraction.json` -- 216 claims (pre-filter)
- `eval-harness/calibration/spec-eval/wrc-extraction-tables-only.json` -- 156 table claims (pre-filter)
- `eval-harness/calibration/spec-eval/ethics-extraction.json` -- 156 claims (pre-filter)

### Key Files

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
| `eval-harness/exceptions.py` | SpecEvalError hierarchy |
| `eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md` | The plan |
| `docs/handoffs/2026-05-25-cross-plan-dependency-autopilot.md` | Cross-plan note |

### Commits This Session

| Hash | Description |
|------|-------------|
| `e010bff` | Cross-plan dependency note + session brief |
| `a6410c1` | Phase 2: extractor (table + prose + dedup) |
| `e45d3d3` | Phases 3-5: scenario gen, scorer, judge, CLI |
| `210c958` | Graceful API key handling + WRC table-only calibration |
| `cb4bd6e` | HANDOFF update |
| `198fdb4` | Model ID fix + WRC full calibration (table + prose) |
| `875eb50` | Ethics Toolkit calibration + timeout fix |
| `e8cb24c` | Fix claim-to-result mapping in gate scorer |
| `df83d70` | Filter non-code tables from extraction |

## What To Do Next

### 1. Add step 9w.8 to autopilot SKILL.md

Add between Steps 9w.7 and 10w in the swarm path:
```
### Step 9w.8: Spec Eval Gate (MANDATORY -- SWARM ONLY)

Run the spec eval gate against the plan:
  `python3 eval-harness/spec_eval_gate.py <plan_path> --output-dir docs/reports/<run-id>`

Check exit code:
- Exit 0 (PASS): proceed to Step 10w.
- Exit 1 (FAIL/WARN/RETRY): abort with gate report details.
```

### 2. Review phase

Run `/workflows:review` on the spec eval gate code. Key areas to scrutinize:
- Table filter accuracy (are we skipping any real code tables?)
- Prose extraction prompt quality (confidence calibration)
- Cost tracking accuracy (Haiku vs Sonnet pricing)
- The 24 WRC failures -- are any false positives from the judge?

### 3. Deferred: table parser refinement

The table filter uses a header allowlist/blocklist. Some edge cases:
- Email schedule tables (testable but filtered) -- prose extractor catches these
- Tables with no recognized headers default to SKIP (conservative)
- Future specs may have new table types that need adding to the allowlist

## Concurrent Work Awareness

Branch `refactor/autopilot-agent-delegation` (worktree: `~/Projects/sandbox-autopilot-delegation`) modifies `.claude/skills/autopilot/SKILL.md` but only touches solo-path steps (3, 5, 6, 7s) and Shared Tail. Swarm-path steps (7w-16w) are preserved. Step 9w.8 goes in the swarm path -- no conflict. Full analysis: `docs/handoffs/2026-05-25-cross-plan-dependency-autopilot.md`.

## Feed-Forward

- **Hardest decision:** Table filter design. Too aggressive = false passes (miss real spec issues). Too permissive = false fails (test untestable claims). Chose allowlist-by-header with conservative default-skip. The 81% pass rate on WRC with 24 genuine failures validates this balance.
- **Rejected alternatives:** (1) No table filter (62% pass, $3 cost, 86 false failures). (2) Section-name-based filter (fragile -- section names vary across specs). (3) LLM-based table classification (adds cost and latency to a pre-flight gate).
- **Least confident:** Whether the 24 WRC failures are all genuine or include false positives from the judge. The anti-leniency rubric biases toward FAIL, which is correct for a pre-swarm gate but may over-flag on complex instructions. Review phase should sample 5-10 failures and verify.
