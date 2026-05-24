---
title: "feat: Pitfall Rule Eval Harness"
type: feat
status: active
date: 2026-05-23
origin: docs/brainstorms/2026-05-23-pitfall-eval-harness-brainstorm.md
swarm: false
feed_forward:
  risk: "Most Tier 1a FCs may score >95%, producing a wall of CLEAR scores. Plan must define what actionable output looks like even when all FCs pass."
  verify_first: true
---

# feat: Pitfall Rule Eval Harness

## Enhancement Summary

**Deepened on:** 2026-05-23
**Research agents used:** best-practices-researcher, framework-docs-researcher, kieran-python-reviewer, architecture-strategist, security-sentinel

### Key Improvements
1. **Batch API integration** -- Anthropic Batch API gives 50% off and eliminates rate-limiting. Full 25-FC run drops from ~$5-6 to ~$2-3. No retry logic needed for batch calls.
2. **Wilson Score Intervals** -- report confidence intervals alongside raw pass rates. With N=5, a 4/5 pass rate has a 95% CI of [30%, 97%]. Honest uncertainty reporting.
3. **Security hardening** -- mandated `yaml.safe_load()`, API key exclusion from all output, cost accumulation per-call (not deferred to scorer).
4. **Pydantic model fixes** -- 2 P1 type issues fixed (timestamp as datetime, consistent `tier` naming), loose `str` fields tightened to `Literal` types.
5. **Architecture clarifications** -- hybrid mode direction (judge only on deterministic FAIL, promotion uses final post-hybrid verdicts only), `CheckResult` frozen dataclass for clean return types, prerequisite fix for FC45/FC46 in source data.

### Prerequisites (must complete before Stage 1)
- **FC45 and FC46 are missing from `agent-pitfalls.md` body** -- reference table has them but no `## Failure Class` heading sections exist. Parser's 47-count validation will fail. **Action:** Add `## Failure Class 45:` and `## Failure Class 46:` sections to `~/.claude/docs/agent-pitfalls.md` with their rule text from the BrewOps run (2026-05-22). This is the sole permitted edit to `agent-pitfalls.md` and must be completed as the first commit before any eval-harness code.

## Overview

A CLI tool that tests whether our 47 agent pitfall rules are clear enough that LLM agents follow them reliably. Runs synthetic coding scenarios per failure class, evaluates agent output via deterministic checks and LLM-as-judge, and produces per-rule adherence scores with promotable regression cases.

Built in two stages: Stage 1 validates the pipeline with 12 deterministic FCs (~$0.40/run). Stage 2 adds 13 hybrid/LLM-judge FCs with calibrated judge (~$5-6/full run). Gate between stages requires Stage 1 to produce a valid report.

Full design rationale: see brainstorm (`docs/brainstorms/2026-05-23-pitfall-eval-harness-brainstorm.md`).

## Plan Quality Gate

1. **What exactly is changing?** Adding `eval-harness/` directory with 7 Python modules, 25 scenario YAML files, 13 judge prompts, calibration set, and CLI entry point.
2. **What must not change?** Existing sandbox apps, autopilot pipeline, any file outside `eval-harness/` -- with one exception: `~/.claude/docs/agent-pitfalls.md` receives a prerequisite edit to add missing FC45/FC46 body sections (see Prerequisites). After that edit, the file is read-only for the remainder of the work phase.
3. **How will we know it worked?** EARS acceptance tests below.
4. **What is the most likely way this plan is wrong?** Most Tier 1a FCs score >95% and the harness produces CLEAR across the board. Mitigation: the with/without-rule delta still ranks rules by injection priority (high delta = load-bearing rule, low delta = redundant injection). Even a wall of CLEAR scores produces a prioritized injection ranking. See "Actionable Output When All FCs Pass" section.

## Actionable Output When All FCs Pass

If every Tier 1a FC scores >95% (CLEAR), the harness still produces:

1. **Injection priority ranking** via with/without-rule delta. FCs where the model already knows the pattern (delta < 5%) are lower priority for brief injection than FCs where the rule changes behavior (delta > 20%). This directly informs which rules to include in space-constrained agent briefs.
2. **Baseline comprehension scores** for each rule. When a rule later fails in a real build, the baseline tells you whether the failure was comprehension (score was always low) or salience (score was high in focused mode, failed under load).
3. **FC4 mixed-signal validation.** If FC4 scores high on comprehension variants, it confirms the spec-omission diagnosis -- remaining FC4 failures are spec problems, not rule problems.
4. **Tier 1b confirmation.** If FC1 and FC35 score >95% as expected, the data supports deprioritizing rule rewrites and investing in spec-completeness-checker improvements instead.

## Implementation Phases

### Stage 1: Pipeline Validation (12 deterministic FCs)

**Goal:** Prove the harness works end-to-end with no LLM judge dependency.

**FCs:** FC7, FC14, FC16, FC19, FC20, FC23, FC24, FC28, FC33, FC36, FC46, FC47

**Implementation order:**
1. `models.py` -- Pydantic models (all data structures)
2. `parser.py` -- FC parser (agent-pitfalls.md -> structured data)
3. 3 pilot scenario files (FC7, FC16, FC47) -- validate schema before writing all 12
4. `runner.py` -- Anthropic API caller
5. `judge.py` -- deterministic checks only (no LLM judge yet)
6. `scorer.py` -- aggregation, buckets, delta computation
7. `reporter.py` -- markdown + JSON output
8. `pitfall_eval.py` -- CLI entry point
9. Remaining 9 scenario files (FC14, FC19, FC20, FC23, FC24, FC28, FC33, FC36, FC46)
10. End-to-end validation: `python pitfall_eval.py --stage 1 --runs 3`

**Gate:** Stage 1 produces a valid report with 12 FC scores, no pipeline crashes. Commit and push before starting Stage 2.

### Stage 2: Full Coverage (adds 13 FCs)

**Goal:** Add LLM-as-judge evaluation and complete 25-FC coverage.

**FCs:**
- Hybrid: FC1, FC4, FC9, FC10, FC15, FC25, FC27, FC35, FC39, FC41
- LLM-judge: FC2, FC17, FC26

**Implementation order:**
1. `judges/base-judge.txt` -- shared judge preamble
2. 13 per-FC judge prompt files
3. `calibration/calibration-set.yaml` -- 20 hand-labeled cases
4. Add LLM judge to `judge.py` (Sonnet, structured output via tool_use)
5. Calibration gate in `pitfall_eval.py` (run calibration before Stage 2 scenarios)
6. 13 scenario YAML files
7. End-to-end validation: `python pitfall_eval.py --all --runs 3`

**Gate:** Calibration accuracy >= 90% (18/20). Full 25-FC report generated.

## File-by-File Specification

### eval-harness/models.py

Pydantic models shared across all modules.

```python
# Key models (see brainstorm for full schema):

class FailureClass(BaseModel):
    """Parsed from agent-pitfalls.md"""
    id: str               # "fc7"
    slug: str             # "route-prefix-doubling"
    name: str             # "Route Prefix Doubling"
    rule_text: str        # The quoted agent rule block
    tier: Literal["1a", "1a-mixed", "1b", "2", "3", "4"]

class Scenario(BaseModel):
    """Loaded from YAML scenario files"""
    id: str
    title: str
    stack: Literal["flask", "express", "nextjs", "supabase", "sqlite", "generic"]
    task_brief: str
    inputs: dict[str, Any]
    context_files: list[str]
    expected_check_type: Literal["deterministic", "llm_judge", "hybrid"]
    expected_outcome: Literal["pass", "fail", "unknown"]
    deterministic_pattern: str | None = None
    deterministic_mode: Literal["presence", "absence"] | None = None
    tags: list[str]
    pair_group: str | None = None
    variant: Literal["with_rule", "without_rule", "adversarial"] = "with_rule"

class ScenarioFile(BaseModel):
    """One YAML file per FC"""
    fc_id: str
    fc_slug: str
    scenarios: list[Scenario]
    # Validators: id prefix, deterministic field consistency, pair group completeness

@dataclasses.dataclass(frozen=True)
class CheckResult:
    """Internal return type for deterministic and judge checks (not serialized to reports)"""
    verdict: Literal["pass", "fail", "error"]
    evidence: str
    confidence: float = 1.0  # 1.0 for deterministic, 0.0-1.0 for judge

class EvalResult(BaseModel):
    """One result per scenario run"""
    scenario_id: str
    fc_id: str
    variant: Literal["with_rule", "without_rule", "adversarial"]
    run_number: int
    verdict: Literal["pass", "fail", "error", "skip"]
    check_type: Literal["deterministic", "llm_judge", "hybrid"]
    evidence: str            # matched pattern or judge reasoning
    confidence: float        # 1.0 for deterministic, 0.0-1.0 for judge
    agent_output: str        # raw code output from Haiku
    prompt_mode: Literal["focused"] = "focused"  # extend to add "swarm_realistic" in v2
    model_id: str            # exact pinned model used
    input_tokens: int
    output_tokens: int
    duration_ms: int

class FCScore(BaseModel):
    """Aggregated score for one FC"""
    fc_id: str
    tier: Literal["1a", "1a-mixed", "1b"]  # consistent with FailureClass.tier
    pass_rate_with_rule: float
    pass_rate_without_rule: float | None = None
    delta: float | None = None  # None when without_rule data is missing
    bucket: Literal["CLEAR", "AMBIGUOUS", "BROKEN"]
    ci_lower: float          # Wilson score interval lower bound (95%)
    ci_upper: float          # Wilson score interval upper bound (95%)
    scenario_count: int
    run_count: int
    promotable_cases: list[str]  # scenario IDs with reproducible failures

class RunReport(BaseModel):
    """Top-level report"""
    timestamp: datetime      # not str -- Pydantic handles serialization
    stage: Literal["1", "2", "all"]
    model_agent: str
    model_judge: str | None
    temperature: float
    max_tokens_agent: int
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    fc_scores: list[FCScore]
    calibration_accuracy: float | None  # Stage 2 only
    report_caveat: str  # mandatory caveat string
```

### eval-harness/parser.py

Parses `~/.claude/docs/agent-pitfalls.md` into `list[FailureClass]`.

**Parsing strategy:**
- Find each `## Failure Class N:` heading (regex: `^## Failure Class \d+:`)
- Extract ID from heading number, slug from `{#fc\d+-...}` anchor
- Extract name from heading text after the colon
- Extract rule text from the `> ` blockquote following `**Agent rule:**` or `**Orchestrator rule:**`
- Skip per-agent-type pitfalls (not numbered FCs)
- Tier assignment: hardcoded lookup table mapping FC ID -> tier (from brainstorm classification)

**Output:** 47 `FailureClass` objects. Parser validates that all 47 IDs from the reference table are found.

**Edge cases:**
- FCs appear out of numeric order in the doc (FC24-FC27 appear after FC32). Parser handles this.
- Some FCs have `**Orchestrator rule:**` instead of `**Agent rule:**`. Parser extracts both.

### eval-harness/runner.py

Calls the Anthropic API with a scenario prompt and returns the agent's code output.

```python
def run_scenario(
    scenario: Scenario,
    fc: FailureClass,
    variant: Literal["with_rule", "without_rule"],
    client: anthropic.Anthropic,
    model: str = "claude-haiku-4-5-20251001",
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> EvalResult:
    """Build prompt, call API, return result.
    Note: runner handles prompt construction + API call + token tracking.
    Verdict comes from judge.py (called by CLI orchestrator after runner returns).
    Implementation may split into runner returning raw output + CLI assembling EvalResult."""
```

**Prompt construction (focused mode):**
```
System: You are a senior {scenario.stack} developer.
Complete the task below.{" Follow the rules provided." if variant == "with_rule" else ""}

{f"Rules:\n{fc.rule_text}" if variant == "with_rule" else ""}

Task:
{scenario.task_brief}

{fixture_content if scenario.context_files else ""}

Respond with ONLY the code. No explanations, no markdown fences.
```

**API settings:**
- Model: `claude-haiku-4-5-20251001` (pinned, not `latest`)
- Temperature: 0.0 (most deterministic)
- Max tokens: 2048
- No system prompt caching (scenarios are short)

**Error handling (complete exception hierarchy):**
- `anthropic.AuthenticationError` (401): abort entire run immediately. Log "Invalid or missing API key" -- never log the exception object (may contain key in headers).
- `anthropic.BadRequestError` (400): record `verdict: "error"`, evidence includes API error message. Do NOT retry (prompt is malformed).
- `anthropic.RateLimitError` (429): exponential backoff respecting `Retry-After` header, 3 retries, then `verdict: "error"`.
- `anthropic.APITimeoutError`: 30s timeout, 2 retries, then `verdict: "error"`.
- `anthropic.OverloadedError` (529): same retry strategy as 429.
- `anthropic.InternalServerError` (500+): 2 retries, then `verdict: "error"`.
- Empty response (0 tokens output): record `verdict: "error"`, evidence: "empty agent output".

**Security requirement:** The API key MUST NOT appear in any output file, JSONL checkpoint, error message, or log line. When catching `AuthenticationError`, log only the message string, not the exception object.

**Cost tracking:** Every call records `input_tokens` and `output_tokens` from `response.usage`. Cost is accumulated per-call in the CLI execution loop (not deferred to scorer). After each `run_scenario()` call, the CLI sums tokens and checks against `--cost-cap`. This prevents the FC41 pattern (cost cap without token accumulation).

### Research Insight: Batch API Mode

The Anthropic Batch API provides **50% cost reduction** and eliminates rate-limiting concerns. Consider adding a `--batch` flag for non-interactive runs:

```python
# Batch mode: submit all scenarios as one batch, poll for results
# - 50% off standard pricing
# - No retry logic needed (batch system handles failures)
# - Results typically available within 1 hour for 750 requests
# - Prompt caching stacks with batch discount (~95% savings on cached system prompt)
batch = client.messages.batches.create(requests=[
    {"custom_id": f"{scenario.id}-{variant}-{run}",
     "params": {"model": MODEL, "max_tokens": 2048, ...}}
    for scenario, variant, run in all_runs
])
```

**V1 recommendation:** Implement synchronous mode first (simpler, immediate results). Add `--batch` as a v1.1 enhancement after the pipeline works. The batch mode is especially valuable for Stage 2 judge calls (Sonnet at 50% off).

### eval-harness/judge.py

Two evaluation paths: deterministic checks and LLM-as-judge.

**Deterministic checks (Stage 1):**
```python
def check_deterministic(output: str, scenario: Scenario) -> CheckResult:
    """Returns CheckResult with confidence=1.0."""
    pattern = scenario.deterministic_pattern
    match = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)

    if scenario.deterministic_mode == "absence":
        # Pattern must NOT appear (e.g., /categories/categories/)
        if match:
            return CheckResult(verdict="fail", evidence=f"Found violation pattern: {match.group()}")
        return CheckResult(verdict="pass", evidence="No violation pattern found")
    else:
        # Pattern MUST appear (e.g., IF NOT EXISTS)
        if match:
            return CheckResult(verdict="pass", evidence=f"Found required pattern: {match.group()}")
        return CheckResult(verdict="fail", evidence=f"Required pattern not found: {pattern}")
```

**Multiple patterns:** Some FCs need multiple checks (e.g., FC16 needs `IF NOT EXISTS` on every `CREATE TABLE`). The scenario YAML `deterministic_pattern` supports regex alternation (`CREATE TABLE(?!.*IF NOT EXISTS)`). If a scenario needs complex multi-pattern logic, use `context_files` to reference a fixture with a custom check function (v2 extension).

**LLM-as-judge (Stage 2):**
```python
def check_with_judge(
    output: str,
    scenario: Scenario,
    fc: FailureClass,
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-6-20250514",
) -> CheckResult:
    """Returns CheckResult with confidence from judge."""
```

Uses Anthropic tool_use to force structured output:
```python
judge_tool = {
    "name": "record_verdict",
    "description": "Record your evaluation verdict",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["pass", "fail"]},
            "evidence": {"type": "string", "description": "Exact quote or pattern from the code that supports your verdict"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
        },
        "required": ["verdict", "evidence", "confidence"]
    }
}
```

Judge prompt is assembled from: `judges/base-judge.txt` + `judges/fc{N}-{slug}.txt` + agent output + rule text.

**Hybrid checks:** Run deterministic first. If deterministic **passes**, accept immediately (no judge call -- saves cost). If deterministic **fails**, run LLM judge to check for false positive. Judge verdict is final when they disagree. This means hybrid mode only invokes the judge on suspected violations, not on clean code.

### Research Insight: YAML Safety Requirement

All YAML loading MUST use `yaml.safe_load()` or `yaml.SafeLoader`. Never `yaml.load()` without `Loader=yaml.SafeLoader`. This applies to scenario files, calibration files, and any future YAML input. `yaml.load()` can deserialize arbitrary Python objects (CWE-502).

### eval-harness/scorer.py

Aggregates `EvalResult` objects into `FCScore` objects.

```python
def score_fc(results: list[EvalResult], fc: FailureClass) -> FCScore:
    """Compute pass rate, delta, bucket, promotable cases for one FC."""

    with_rule = [r for r in results if r.variant == "with_rule" and r.verdict != "error"]
    without_rule = [r for r in results if r.variant == "without_rule" and r.verdict != "error"]

    if not with_rule:
        return None  # all results errored -- skip this FC with a warning
    pass_rate_with = sum(1 for r in with_rule if r.verdict == "pass") / len(with_rule)
    pass_rate_without = sum(1 for r in without_rule if r.verdict == "pass") / len(without_rule) if without_rule else None

    delta = pass_rate_with - pass_rate_without if pass_rate_without is not None else None

    # Scoring buckets
    if pass_rate_with > 0.95:
        bucket = "CLEAR"
    elif pass_rate_with >= 0.70:
        bucket = "AMBIGUOUS"
    else:
        bucket = "BROKEN"

    # Promotable cases: reproducible failures with strong evidence
    promotable = find_promotable_cases(with_rule)

    # Wilson Score Interval for honest uncertainty at small N
    ci_lower, ci_upper = wilson_score_interval(
        successes=sum(1 for r in with_rule if r.verdict == "pass"),
        n=len(with_rule),
    )

    return FCScore(ci_lower=ci_lower, ci_upper=ci_upper, ...)
```

### Research Insight: Statistical Honesty at Small N

With N=5 runs per scenario (15 total data points per FC at 5 scenarios x 3 runs), naive pass rates are misleading. Use **Wilson Score Intervals** for confidence bounds:

```python
def wilson_score_interval(successes: int, n: int) -> tuple[float, float]:
    """Wilson score 95% CI -- much better than normal approximation for small N."""
    if n == 0:
        return (0.0, 1.0)
    z = 1.96  # hardcoded for 95% confidence, no scipy needed
    p_hat = successes / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))
    return (max(0.0, center - margin), min(1.0, center + margin))

# Example: 4 out of 5 passes -> 95% CI: [30%, 97%]. That wide range IS the reality.
```

The report must show CI bounds alongside pass rates. A score of "80% [30%-97%]" communicates very different confidence than a bare "80%." This prevents over-interpretation of small-sample results.

**Implementation note:** The formula uses z=1.96 (hardcoded for 95% confidence). No scipy dependency needed.

**Promotable case detection (see brainstorm: promotion criteria):**

Promotion is always based on **final verdicts** (post-hybrid resolution), never on intermediate pre-check results. For hybrid FCs, a deterministic pre-check failure that the judge overturns does NOT count toward promotion.

- **Deterministic FCs:** scenario has final verdict FAIL in 2+ of 3 runs (deterministic is the only check, so final = deterministic).
- **Hybrid FCs:** scenario has final verdict FAIL in 2+ of 3 runs. Final verdict = deterministic if it passed, or judge verdict if deterministic failed and judge was invoked.
- **LLM-judge FCs:** scenario has final verdict FAIL with judge confidence >= 0.8 in 2+ of 3 runs.
- Cases meeting these criteria are listed by scenario ID in the report.

### eval-harness/reporter.py

Generates markdown report + JSON data file.

**Markdown report structure:**
```markdown
# Pitfall Rule Eval Report
> These results estimate rule clarity/comprehension under controlled prompting.
> They do not estimate adherence under realistic swarm cognitive load.

## Run Metadata
- Date: {timestamp}
- Stage: {stage}
- Agent model: {model_agent}
- Judge model: {model_judge}
- Temperature: {temperature}
- Total cost: ${total_cost_usd:.2f}
- Calibration accuracy: {calibration_accuracy} (Stage 2 only)

## Results Summary

| FC | Type | With Rule | 95% CI | Without Rule | Delta | Bucket | Promotable |
|----|------|-----------|--------|-------------|-------|--------|------------|
| FC7 | 1a | 100% | [78%-100%] | 60% | +40% | CLEAR | -- |
| FC4 | 1a-mixed | 93% | [70%-99%] | 85% | +8% | AMBIGUOUS | fc4-flask-patch-norule |
| FC1 | 1b | 98% | [76%-100%] | 95% | +3% | CLEAR | -- |

## Injection Priority (by delta, descending)
[FCs ranked by delta value -- highest delta = most load-bearing rule]

## Promotable Cases
[Scenario details for each promotable case]

## Per-FC Details
[Expandable sections with individual scenario results]
```

**JSON output:** Full `RunReport` model serialized to JSON, written alongside the markdown.

**Output location:** `eval-harness/reports/{YYYY-MM-DD-HHmm}-{stage}.md` and `.json`.

### eval-harness/pitfall_eval.py

CLI entry point using `click`.

```python
@click.command()
@click.option("--stage", type=click.Choice(["1", "2", "all"]), default="1",
              help="Stage 1 (deterministic only) is the safe default")
@click.option("--fc", type=str, default=None, help="Run single FC (e.g., fc7)")
@click.option("--runs", type=int, default=3, help="Runs per scenario")
@click.option("--pitfalls", type=click.Path(exists=True),
              default=str(Path.home() / ".claude" / "docs" / "agent-pitfalls.md"))
@click.option("--output-dir", type=click.Path(), default="reports",
              help="Directory for report output")
@click.option("--model-agent", type=str, default="claude-haiku-4-5-20251001",
              help="Pinned model for agent under test")
@click.option("--model-judge", type=str, default="claude-sonnet-4-6-20250514",
              help="Pinned model for LLM judge")
@click.option("--dry-run", is_flag=True, help="Validate scenarios without API calls")
@click.option("--resume", type=str, default=None, help="Resume from run-id (JSONL checkpoint)")
@click.option("--cost-cap", type=float, default=10.0, help="Max USD per run")
@click.option("--verbose", is_flag=True)
def main(stage, fc, runs, pitfalls, output_dir, model_agent, model_judge,
         dry_run, resume, cost_cap, verbose):
    """Pitfall Rule Eval Harness -- test agent rule clarity."""
```

**Execution flow:**
1. Parse agent-pitfalls.md
2. Load and validate all scenario YAML files
3. Validate ANTHROPIC_API_KEY exists in environment
4. If `--dry-run`: report scenario count, estimated cost, exit
5. If `--stage 2` or `--all`: run calibration gate first
6. For each FC in scope: run all scenarios x variants x runs
7. Show progress with `rich.progress` bar (FC name, scenario count, elapsed time)
8. Accumulate cost; abort if `--cost-cap` exceeded
9. Score and report
10. Write report files

**Checkpoint/resume:** Results are written incrementally to a JSONL file (`reports/{run-id}.jsonl`). On restart, existing results are loaded and skipped. This prevents losing partial results on API errors or interruptions.

### eval-harness/scenarios/

One YAML file per FC. See brainstorm for complete schema and example (FC7).

**Stage 1 files (12):**
```
fc7-route-prefix-doubling.yaml
fc14-executescript-destructive.yaml
fc16-non-idempotent-ddl.yaml
fc19-unsigned-tokens.yaml
fc20-cron-no-concurrency.yaml
fc23-anon-rls-enumeration.yaml
fc24-xml-sandbox-no-escape.yaml
fc28-proxy-path-stripping.yaml
fc33-transitive-dep.yaml
fc36-fts5-operator-injection.yaml
fc46-phantom-fk.yaml
fc47-markup-xss-bypass.yaml
```

**Stage 2 files (13):**
```
fc1-naming-divergence.yaml
fc2-wrong-usage-inferred.yaml
fc4-validation-gap.yaml
fc9-mock-mismatch.yaml
fc10-fail-open.yaml
fc15-window-location-ssr.yaml
fc17-duplicate-boilerplate.yaml
fc25-zip-decompression-bomb.yaml
fc26-comment-not-code.yaml
fc27-neighbor-pattern-skip.yaml
fc35-idor-ownership-check.yaml
fc39-app-per-job-worker.yaml
fc41-cost-cap-no-tokens.yaml
```

Each file contains 5 unique scenarios with paired with/without-rule variants (10 total entries per file).

### eval-harness/judges/

**base-judge.txt:** Shared preamble for all judge prompts.
```
You are evaluating whether a code sample follows a specific rule.

You will receive:
1. The rule text
2. The code to evaluate
3. FC-specific evaluation guidance

Use the record_verdict tool to report your finding.
- verdict: "pass" if the code follows the rule, "fail" if it violates it
- evidence: quote the exact code that demonstrates compliance or violation
- confidence: 0.0 (uncertain) to 1.0 (certain)
```

**Per-FC judge files (13):** `fc{N}-{slug}.txt` with FC-specific guidance on what the violation looks like, what correct code looks like, and common false positives.

### eval-harness/calibration/calibration-set.yaml

20 hand-labeled cases: 10 clear violations + 10 clear passes. Must span at least 5 of the 13 judge FCs. Each case includes:
```yaml
- id: cal-fc26-missing-impl
  fc_id: fc26
  agent_output: |
    # Security: All user content is XML-sandboxed per brainstorm Gap 2
    def process_content(content):
        return f"<content>{content}</content>"
  expected_verdict: fail
  label_rationale: "Comment claims sandboxing but escape function is missing"
```

Calibration threshold: >= 90% (18/20 passes the gate). Calibration results are included in every report.

## Implementation Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| Agent model | `claude-haiku-4-5-20251001` | Pinned for reproducibility. Cheapest Claude model = "most likely to fail" baseline. |
| Judge model | `claude-sonnet-4-6-20250514` | Different model family reduces correlated blindspots. |
| Temperature | 0.0 | Most deterministic output for stable pass rates. |
| Max tokens (agent) | 2048 | Sufficient for single-file code output. |
| Max tokens (judge) | 1024 | Judge needs less output than agent. |
| Default runs | 3 | Balances statistical signal vs cost. |
| Cost cap | $10.00 | Full run is ~$5-6; cap provides 2x headroom. |
| API timeout | 30 seconds | Per-call timeout. |
| Max retries | 3 | Exponential backoff on rate limit / timeout. |
| Calibration threshold | >= 90% (18/20) | Inclusive. 18/20 passes the gate. |
| CLEAR bucket | > 95% pass | Rule is well-written. |
| AMBIGUOUS bucket | 70-95% pass | Rewrite candidate. |
| BROKEN bucket | < 70% pass | Priority rewrite. |

## Acceptance Tests

### Stage 1

- WHEN the parser reads `agent-pitfalls.md` THE SYSTEM SHALL extract exactly 47 FailureClass objects with non-empty rule_text
- WHEN a scenario YAML file has an invalid field THE SYSTEM SHALL exit with an error naming the file and invalid field
- WHEN a scenario ID does not start with its fc_id THE SYSTEM SHALL reject the file at load time
- WHEN a pair_group has a with_rule variant but no without_rule variant THE SYSTEM SHALL reject the file at load time
- WHEN the harness runs `--stage 1 --runs 3` THE SYSTEM SHALL produce a JSON report with 12 FC scores
- WHEN a deterministic check finds a violation pattern in agent output THE SYSTEM SHALL record verdict "fail" with the matched pattern as evidence
- WHEN a deterministic check finds no violation pattern THE SYSTEM SHALL record verdict "pass"
- WHEN the API returns a rate limit error THE SYSTEM SHALL retry with exponential backoff up to 3 times
- WHEN the API key is missing THE SYSTEM SHALL abort immediately with "ANTHROPIC_API_KEY not set"
- WHEN `--dry-run` is passed THE SYSTEM SHALL report scenario count and estimated cost without making API calls
- WHEN cumulative cost exceeds `--cost-cap` THE SYSTEM SHALL abort and produce a partial report (completed FCs only, with a "cost-capped" note in report header)
- WHEN a single scenario completes THE SYSTEM SHALL have cumulative cost > $0.00 (FC41 self-check)
- WHEN a JSONL checkpoint file is truncated or contains malformed lines THE SYSTEM SHALL skip bad lines with a warning and resume from valid entries
- WHEN `--resume {run-id}` is passed THE SYSTEM SHALL load existing results from `{run-id}.jsonl`, skip completed scenarios, and continue from where the prior run stopped

### Stage 2

- WHEN the calibration set accuracy is < 90% THE SYSTEM SHALL abort Stage 2 with "calibration failed: {accuracy}%"
- WHEN the calibration set accuracy is >= 90% THE SYSTEM SHALL proceed with Stage 2 scenarios
- WHEN the LLM judge evaluates agent output THE SYSTEM SHALL return structured output via tool_use with verdict, evidence, and confidence
- WHEN a hybrid check's deterministic check passes THE SYSTEM SHALL accept the pass verdict without invoking the LLM judge
- WHEN a hybrid check's deterministic pre-check fails THE SYSTEM SHALL invoke the LLM judge before finalizing the verdict
- WHEN the LLM judge overturns a deterministic pre-check failure THE SYSTEM SHALL use the judge verdict as the final result and SHALL NOT count the pre-check failure toward promotion
- WHEN an FC is type `1a-mixed` THE SYSTEM SHALL annotate it as `1a-mixed` in the report type column
- WHEN an FC is type `1b` THE SYSTEM SHALL annotate it as `1b` in the report type column

### Report

- WHEN all 25 FCs complete THE SYSTEM SHALL produce a results table sorted by delta (descending)
- WHEN any FC scores AMBIGUOUS or BROKEN THE SYSTEM SHALL highlight it in the report summary
- WHEN a scenario has a final verdict of FAIL in 2+ of 3 runs (deterministic or hybrid FCs) THE SYSTEM SHALL list it as a promotable case
- WHEN a scenario has a final verdict of FAIL with judge confidence >= 0.8 in 2+ of 3 runs (LLM-judge FCs) THE SYSTEM SHALL list it as a promotable case
- EVERY report SHALL include the caveat: "These results estimate rule clarity/comprehension under controlled prompting. They do not estimate adherence under realistic swarm cognitive load."
- EVERY report SHALL include the run metadata: timestamp, models, temperature, total cost

### Verification Commands

```bash
# Stage 1 dry run (default stage is "1")
cd eval-harness && python pitfall_eval.py --dry-run

# Stage 1 full run
cd eval-harness && python pitfall_eval.py --runs 3

# Single FC test
cd eval-harness && python pitfall_eval.py --fc fc7 --runs 1

# Full run (both stages)
cd eval-harness && python pitfall_eval.py --stage all --runs 3

# Resume a partial run
cd eval-harness && python pitfall_eval.py --resume 2026-05-23-1430

# Verify report exists
ls eval-harness/reports/*.md
```

## Dependencies

Already installed in sandbox Python environment:
- `anthropic` (0.89.0) -- API client
- `pydantic` (2.12.5) -- model validation
- `PyYAML` (6.0.3) -- scenario loading (MUST use `yaml.safe_load()`)
- `rich` (14.3.3) -- progress bars, CLI output
- `click` (8.3.2) -- CLI framework

**No new dependencies.** Wilson score interval is implemented manually using `math` with z=1.96 (hardcoded for 95% confidence). This avoids adding scipy (~40MB) for a 10-line formula.

## Alternative Approaches Considered

(see brainstorm: Rejected alternatives)

1. **Full benchmarking platform with web dashboard** -- too broad for v1. CLI is sufficient.
2. **Adversarial-first approach** -- generating hard scenarios before validating basic ones is premature.
3. **Integration with autopilot pipeline** -- couples two systems before either is stable.
4. **Single universal judge prompt** -- too general to catch FC-specific violations. Per-FC prompts are more accurate.
5. **Same model for agent and judge** -- correlated blindspots. Haiku agent + Sonnet judge mitigates this.
6. **FC4 as pure Tier 1b** -- hides real comprehension failures. `1a-mixed` annotation keeps scores actionable.
7. **Building all 25 FCs before validating pipeline** -- risks wasted scenario authoring. Two-stage build de-risks.

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-05-23-pitfall-eval-harness-brainstorm.md](docs/brainstorms/2026-05-23-pitfall-eval-harness-brainstorm.md)
  - Key decisions: FC tier classification (23 Tier 1a + 2 Tier 1b), two-stage build, focused prompt mode, YAML-per-FC scenarios, per-FC judge prompts, strong-evidence promotion criteria
  - 3 rounds of Codex review, all PASS

### Internal References

- Agent pitfalls: `~/.claude/docs/agent-pitfalls.md` (47 FCs, prerequisite edit for FC45/FC46 then read-only)
- Spec-completeness checker: `docs/solutions/2026-05-21-spec-completeness-checker-pre-swarm-gate.md` (FC1/FC4/FC35 spec-omission root cause)
- Autonomy hardening: `docs/solutions/2026-05-13-sandbox-autonomy-hardening.md` (stable keys pattern, self-audit design)
- Spec convergence loop: `docs/solutions/2026-04-30-spec-convergence-loop.md` (multi-tool validation, calibration convergence)

### Lessons Applied

- **Hard gates over prose reminders** (FC11 solution): Stage 1 -> Stage 2 gate is a hard check, not a comment
- **Stable result keys** (autonomy hardening): result keys use `{fc_id}-{scenario_id}-{variant}-{run_num}`
- **Judge calibration** (spec convergence): 20-case set with human labels, run before every batch

## Feed-Forward

- **Hardest decision:** Whether to implement checkpoint/resume for partial runs. Added it (JSONL incremental writes) because a rate-limit error at 80% completion would waste ~$4 of API spend and ~30 minutes of wall time. The complexity cost is low (read existing JSONL, skip completed scenarios).
- **Rejected alternatives:** (1) In-memory-only results with full re-run on failure -- wasteful at scale. (2) SQLite result store -- overengineered for v1; JSONL is simpler and human-readable.
- **Least confident:** Whether the Pydantic scenario schema is flexible enough for all 25 FCs without needing per-FC schema extensions. The `inputs: dict[str, Any]` field is a catch-all, but some FCs (FC27 neighbor-pattern-skip, FC9 mock-mismatch) need rich context that may strain the YAML authoring format. If >3 scenarios require >20-line fixture files, the `fixtures/` directory will need clearer naming conventions than currently specified.

## Codex Handoff

```
Read docs/plans/2026-05-23-feat-pitfall-eval-harness-plan.md.

This plan was deepened with 5 research/review agents. Enhancement Summary
is at the top. Review for:

1. Does every brainstorm decision appear in the plan? Cross-reference against
   docs/brainstorms/2026-05-23-pitfall-eval-harness-brainstorm.md.
2. Are the EARS acceptance tests complete? Check the new tests added from
   deepening (cost accumulation FC41 self-check, corrupted JSONL handling).
3. Are the Pydantic model fixes correct? (CheckResult dataclass, Literal types
   on EvalResult, datetime timestamp, float|None on delta/pass_rate_without).
4. Is the hybrid mode direction clear? (deterministic PASS = final, judge only
   on deterministic FAIL).
5. Does the Wilson CI integration make sense? Is the report table with CI
   bounds readable?
6. Is the Batch API recommendation appropriately scoped as v1.1 (not v1)?
7. Are the security requirements (yaml.safe_load, API key exclusion, per-call
   cost accumulation) explicit enough to implement?
8. Is the FC45/FC46 prerequisite (source data bug) clearly flagged?
9. Final gate: is this plan ready for /workflows:work?

Output: findings with severity or approval to proceed.
```
