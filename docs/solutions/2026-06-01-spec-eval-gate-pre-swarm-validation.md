---
title: Spec Eval Gate -- Pre-Swarm Validation That Agents Can Follow Spec Instructions
date: 2026-06-01
status: complete
problem_type: false-pass-factory
component: eval-harness
symptoms:
  - Runs 046-052 produced 1-2 P1s each despite documented agent pitfall rules
  - Spec completeness checker (9w.6) confirmed sections existed but agents still produced non-compliant code
  - Ambiguous spec prose caused inconsistent agent behavior (e.g., "validate email" without specifying how)
root_cause: Spec completeness checks confirm structure (sections exist) but not executability (agents can follow the instructions). Ambiguous or vague spec prose passes structural checks but produces non-compliant code.
solution_type: pre-launch-gate
tags:
  - spec-eval
  - pre-swarm-gate
  - llm-as-judge
  - claim-extraction
  - eval-harness
  - autopilot
related_runs:
  - run-046
  - run-047
  - run-048
  - run-049
  - run-050
  - run-051
  - run-052
related_solutions:
  - docs/solutions/2026-05-21-spec-completeness-checker-pre-swarm-gate.md
  - docs/solutions/2026-04-30-spec-convergence-loop.md
  - docs/solutions/2026-05-05-venue-scraper-llm-extraction-pipeline.md
  - docs/solutions/2026-05-13-sandbox-autonomy-hardening.md
feed_forward:
  risk: "Anti-leniency judge may produce false positives on complex multi-step instructions. The 81% pass rate on WRC spec includes 24 failures that need human triage to confirm they are all genuine."
  verify_first: true
---

# Spec Eval Gate -- Pre-Swarm Validation That Agents Can Follow Spec Instructions

## Problem

The autopilot pipeline had two pre-swarm validation layers:
1. **Spec completeness checker (9w.6):** Confirms the spec has the right sections (Export Names, Authorization Matrix, etc.)
2. **Pitfall eval + Monte Carlo (9w.7):** Tests whether agents follow generic pitfall rules

Neither answered the critical question: **"Can an agent actually execute this spec's concrete instructions?"**

Runs 046-052 demonstrated the gap. Each spec passed completeness checks but produced 1-2 P1s from ambiguous instructions. When a spec says "validate email" without specifying how, the completeness checker sees a validation section and PASSes. But agents either skip validation or implement it inconsistently.

The failure loop: spec passes structural check -> agents produce structurally-complete but semantically-wrong code -> review catches P1 -> fix applied -> next spec has a different ambiguity -> repeat.

## Root Cause

Structural completeness and execution fidelity are different properties. A spec can have all 6 mandatory sections (Export Names, Cross-Boundary Wiring, Input Validation, Coordinated Behaviors, Transaction Contracts, Authorization Matrix) yet still contain ambiguous instructions within those sections.

The completeness checker operates at the section level. The spec eval gate operates at the instruction level -- it tests each concrete claim individually.

## Solution

A new pre-swarm gate (step 9w.8) that extracts testable claims from spec tables and prose, generates scenarios from them, runs the scenarios through a Haiku agent, judges the agent's output with a Sonnet anti-leniency judge, and blocks the swarm if agents can't reliably follow the spec.

### Pipeline

```
spec.md
  |
  v
extractor.py
  parse_tables() -----> table claims (confidence=1.0, deterministic)
  strip_tables() -----> prose without tables (20-40% fewer tokens)
  extract_prose_claims() -> prose claims (calibrated confidence)
  deduplicate_claims() --> merged claim list
  |
  v
spec_scenario_gen.py
  claims_to_scenarios() -> (Scenario, rule_text) pairs
  |
  v
runner.py (existing, refactored: accepts rule_text: str)
  + spec_judge.py (new: anti-leniency rubric, richer tool schema)
  |
  v
spec_scorer.py
  score_gate() -> GateResult (PASS / FAIL / WARN_UNSCORABLE / RETRY)
```

### Key Design Decisions

**1. Hybrid extraction (deterministic tables + targeted LLM prose)**

Tables are parsed with regex (confidence=1.0, no API cost). Tables are then stripped from the spec text before sending to Sonnet for prose extraction. This reduces Sonnet input by 20-40% on table-heavy specs.

Why not LLM-only extraction? Tables have structured, predictable formats. Parsing them deterministically is cheaper, faster, and more reliable. The LLM is reserved for the hard part: extracting concrete claims from narrative prose.

**2. Table filter: allowlist-by-header with conservative default-skip**

Not all tables in a spec are code-testable. Decision tables, agent assignment tables, and data ownership tables describe project management, not code. Without filtering, the WRC spec produced 156 raw table claims with a 62% pass rate and 86 false failures. After filtering to 55 code-testable claims (using an allowlist of headers like Route, Function, Export, Field, Validation), the pass rate rose to 81% with 24 genuine failures.

The allowlist checks for headers matching code concepts (`route`, `function`, `export`, `field`, `input`, `validation`, `error response`, `constraint`, `type`, `returns`, `limit`, `scope`). Unknown table types are skipped by default (conservative).

**3. Confidence-filtered 100% threshold**

Claims are partitioned into HIGH (>= 0.90 confidence) and LOW (< 0.90). ALL HIGH claims must pass for the gate to PASS. LOW claims are reported as warnings but never block.

Why 0.90 and not 0.85? LLMs are systematically overconfident (ECE 0.10-0.30). A raw 0.85 from an LLM often corresponds to ~0.70 true calibration. 0.90 catches this bias. Table claims always get 1.0 (no calibration needed).

**4. Anti-leniency judge (not the existing pitfall judge)**

The spec-eval judge has its own prompt (`judges/spec-eval-base.txt`) with rules designed for spec instruction adherence, not pitfall rule adherence. Key differences:
- Naming claims are EXACT: `list_tasks` != `listTasks` != `ListTasks`
- Default to FAIL unless specific code lines are quoted as evidence
- No "unclear" verdict option -- forces binary pass/fail
- Chain-of-thought (`reasoning`) comes before `verdict` in the tool schema (debiasing)
- `supporting_evidence` field requires quoting code lines (prevents "probably handles it elsewhere")

**5. Runner refactor: accept `rule_text: str` instead of `FailureClass`**

The brainstorm initially proposed wrapping claims in synthetic `FailureClass` objects to avoid modifying `runner.py`. Plan deepening (7-agent research) found two bugs in this approach: `tier: 0` crashes Pydantic validation, and `variant="spec_adherence"` silently prevents `build_prompt()` from injecting `rule_text` (only `variant="with_rule"` injects it). The 4-line refactor to accept `rule_text: str` directly was safer.

**6. Async orchestration with sync client**

Scenarios run concurrently via `asyncio.gather` + `Semaphore(5)`. Each scenario is wrapped in `asyncio.to_thread()` using the synchronous `anthropic.Anthropic` client (which is thread-safe). This avoids introducing `AsyncAnthropic` while achieving 4x throughput improvement (15 scenarios: 2 min sequential -> 25 sec concurrent).

### Patterns Established

**Table filter pattern:** When extracting structured data from specs, allowlist the table types by recognizing header patterns (code-testable headers like Route/Function/Export vs. management headers like Decision/Phase/Writer). Default to skip on unrecognized headers.

**Confidence-filtered threshold pattern:** When mixing deterministic extraction (high confidence) with LLM extraction (variable confidence), partition by confidence tier. Gate on the high tier. Report the low tier as non-blocking warnings. This prevents noisy LLM claims from blocking the pipeline while still surfacing them for human review.

**Anti-leniency judge pattern:** When using LLM-as-judge for strict adherence checks, put reasoning before verdict in the tool schema, require evidence quoting, eliminate "unclear" as an option, and default to FAIL. The bias should match the gate's purpose: a pre-swarm gate should be strict (false negatives are cheaper than false positives).

**Cost aggregation after gather:** When running concurrent API calls with a cost tracker, do NOT update a shared mutable cost counter from inside tasks. Instead, return costs from each task and aggregate sequentially after `asyncio.gather` completes. This eliminates race conditions on the cost counter.

**Verification artifact pattern:** When a gate passes, write a machine-checkable artifact (`spec-eval-verification.md`) that downstream steps can check for. This prevents gate-bypass bugs where the pipeline continues despite a missing or failed gate run (the Run-054 pattern).

**Exit code hygiene:** Use distinct exit codes for different failure modes. Exit 0 = PASS, exit 1 = FAIL/WARN/RETRY (spec problem), exit 2 = ENV_ERROR (missing API key, not a spec problem). This prevents wasting a retry on an environment error that won't resolve itself.

## Results

| Metric | Value |
|--------|-------|
| WRC spec: total claims | 130 (55 table + 75 prose) |
| WRC spec: HIGH passed | 102/126 (81%) |
| WRC spec: genuine failures | 24 (mock APIs, missing routes, incorrect validation) |
| WRC spec: cost | $0.90 |
| WRC spec: runtime | ~6.5 min |
| Ethics Toolkit: claims extracted | 156 (dry-run calibration) |
| New files | 7 (extractor, scenario_gen, scorer, judge, gate, exceptions, judge prompt) |
| Modified files | 3 (runner.py ~14 lines, pitfall_eval.py ~4 lines, models.py ~70 lines) |

## P1s Found in Review (Fixed)

| # | Finding | Root Cause | Fix |
|---|---------|-----------|-----|
| 1 | CostTracker race condition | Shared mutable `total_cost` updated from concurrent tasks | Aggregate costs after `asyncio.gather` completes |
| 2 | Missing verification artifact | No file written on PASS, downstream step 10w couldn't verify gate ran | Write `spec-eval-verification.md` on PASS |
| 3 | Exit code ambiguity | Exit 1 for both spec failures and env errors | Exit 2 for env errors (missing API key) |

All three P1s were independently predicted by prior solution docs (venue-scraper cost pattern, autonomy-hardening verification pattern). The solution doc system works -- these patterns recur.

## What This Does NOT Solve

- **False positives from anti-leniency judge:** The 24 WRC failures need human triage. Some may be legitimate spec ambiguities that the judge correctly flags; others may be overly strict naming checks on complex multi-step instructions.
- **Prose extraction quality on novel spec formats:** Tested on WRC (dense, 1300+ lines) and Ethics Toolkit (moderate). Untested on specs with unusual formatting, embedded diagrams, or non-English content.
- **Judge consistency across runs:** LLM judges are non-deterministic. The same claim may get different verdicts on different runs. The confidence filter mitigates this but doesn't eliminate it.

## Feed-Forward

- **Hardest decision:** Table filter design. Allowlist-by-header with conservative default-skip. Validated by the 81% pass rate with 24 genuine failures vs. 62% without filtering.
- **Rejected alternatives:** No filter (62%, $3, 86 false failures). Section-name filter (fragile -- heading text varies). LLM classification of tables (adds cost to a pre-flight gate). Percentage threshold >= 80% (waters down the gate).
- **Least confident:** Whether the 24 WRC failures include false positives from the anti-leniency judge. The judge biases toward FAIL, which is correct for a pre-swarm gate but may over-flag complex instructions. First real swarm run using this gate will calibrate.
