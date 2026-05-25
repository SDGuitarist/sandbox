---
title: "Eval Harness Ultrareview Findings"
date: 2026-05-24
source: ultrareview of sandbox#9 (ran against full repo, findings are eval-harness only)
target_branch: feat/pitfall-eval-harness
status: pending
---

# Eval Harness Ultrareview Findings

These 6 bugs were found during the CPAA Shadow Lab PR ultrareview but all belong to `eval-harness/` on `feat/pitfall-eval-harness`. None affect the CPAA code.

## bug_011 (normal): Resume doesn't restore cost/token accumulators

**File:** `eval-harness/pitfall_eval.py:315-330`

When resuming from checkpoint, `total_cost`, `total_input_tokens`, `total_output_tokens` stay at 0. The checkpoint loading loop only appends to `all_results` without summing token/cost fields. Result: cost cap allows 2x budget on resumed runs, final report underreports spend.

**Fix:** After the checkpoint loading loop (after line 330), sum tokens and costs from loaded results:
```python
for r in all_results:
    total_input_tokens += r.input_tokens
    total_output_tokens += r.output_tokens
    total_cost += estimate_cost(model_agent, r.input_tokens, r.output_tokens)
```

## merged_bug_001 (normal): Calibration gate non-functional

**Files:** `eval-harness/pitfall_eval.py:45`, calibration-set.yaml

Three compounding issues:
1. `CALIBRATION_THRESHOLD = 0.85` but plan specifies 0.90 (18/20)
2. Calibration set uses Stage 1 deterministic FCs, not Stage 2 judge FCs as plan requires
3. `--stage 2` never auto-runs calibration — `--calibrate` is a separate code path that exits immediately

**Fix:** Change threshold to 0.90, replace calibration samples with Stage 2 judge FC samples, add auto-calibration when stage is "2" or "all".

## bug_016 (normal): Hybrid scenarios bypass LLM confidence gate

**File:** `eval-harness/scorer.py:38-48`

`find_promotable_cases()` only applies the >= 0.8 confidence gate when `check_type == "llm_judge"`, but hybrid scenarios keep `check_type` as `"hybrid"` throughout the pipeline. Low-confidence hybrid fails get promoted unconditionally.

**Fix:** Change line 39 from `check_type == "llm_judge"` to `check_type in ("llm_judge", "hybrid")`.

## merged_bug_014 (normal): Overly broad deterministic patterns

**Files:** 3 scenario YAMLs

1. **fc36-venue-search** (line 14): Pattern includes `".*"` which with `re.DOTALL` matches any Python output containing double-quoted strings
2. **fc16-sqlite-create-multi** (line 119): Pattern only checks `CREATE TABLE`, misses bare `CREATE INDEX` without `IF NOT EXISTS`
3. **fc10-secret-key-missing** (line 17): Pattern `raise|RuntimeError|sys\.exit|fatal` too broad for Flask apps — any unrelated `raise` triggers false pass

## merged_bug_006 (normal): Judge costs not tracked + FC41 self-check dead code

**Files:** `eval-harness/pitfall_eval.py:366-372`, `eval-harness/judge.py`

1. LLM judge API calls (Sonnet) never have token usage recorded — `response.usage` is discarded. Stage 2 runs could undercount costs by 50%+.
2. FC41 self-check on line 371 (`total_cost <= 0 and result.input_tokens > 0`) is dead code — `total_cost` is already positive from line 369.

## merged_bug_003 (nit): Unpinned judge model + not recorded in report

**File:** `eval-harness/judge.py:12`

`JUDGE_MODEL = "claude-sonnet-4-6"` instead of plan-specified `claude-sonnet-4-6-20250514`. Also, `model_judge` is always `None` in RunReport.
