---
title: "Pitfall Rule Eval Harness"
date: 2026-05-23
status: brainstorm
tags: [eval, testing, agent-pitfalls, simulation, rule-quality]
feed_forward:
  risk: "Real-world FC failures have three causes (clarity, salience, spec-omission) but v1 focused mode only measures clarity. High pass rates may reflect that clarity was never the bottleneck for most FCs."
  verify_first: true
---

# Pitfall Rule Eval Harness -- Brainstorm

## What We're Building

A simulation-based rule adherence harness that measures whether our 47 agent pitfall rules are clear enough that LLM agents follow them reliably. The harness generates synthetic coding scenarios per failure class, runs an LLM agent against them (with the rule injected), uses a combination of deterministic checks and LLM-as-judge evaluation, and produces per-rule adherence scores, ambiguity reports, and promotable regression cases.

**V1 scope:** Rule quality testing only, built in two stages:
- **Stage 1 (pipeline validation):** 12 deterministic-only FCs. No judge prompts needed. Validates parser, runner, deterministic checks, scorer, reporter, CLI end-to-end.
- **Stage 2 (full coverage):** Add 11 hybrid/LLM-judge FCs + 2 Tier 1b FCs = 25 total. Requires judge prompts, calibration set, LLM-as-judge evaluation.
- **Gate:** Stage 2 starts only after Stage 1 produces a valid report with no pipeline errors.

Build recommender and adversarial modes are future consumers of the data, not v1 goals.

## Why This Approach

### Problem Statement

Full autopilot builds give ~1 data point per FC per build. 18 builds over 7 weeks means many FCs have been hit only 1-2 times. We can't know if a rule written after a single incident is actually clear enough to prevent recurrence -- we're waiting for the next organic occurrence, which might be weeks away.

Simulation gives N=100+ data points per FC in minutes, not months. It isolates rule clarity from context pressure, multi-agent coordination, and tool interaction -- variables that full builds can't control for.

### What This Harness Cannot Claim

- Rules that pass simulation will work in real builds (simulation tests comprehension, not execution under pressure)
- FC coverage in simulation equals FC coverage in production (Tier 3 FCs can't be simulated)
- High adherence score means the rule is sufficient (the rule might be clear but the FC might have variants it doesn't cover)
- Full builds are replaceable (simulation is the unit test for rule quality; full builds are the integration test)

### Over-Trust Risks

1. **Correlated blindspots.** Agent and judge are both Claude family. Shared misinterpretation = 100% pass on a broken rule.
2. **Scenario cleanliness bias.** Real failures emerge from messy multi-agent interactions, not clean code snippets.
3. **Teaching to the test.** Rules might pass hand-written scenarios but fail on real-world variants.

## Key Decisions

### FC Tier Classification

Every one of the 47 FCs appears exactly once. Totals: 23 + 2 + 16 + 4 + 2 = 47.

**Tier 1a: Rule-clarity testing (23 FCs)** -- rule comprehension is the bottleneck, single-file code-output scenarios work, simulation directly measures the right thing:
FC2, FC4*, FC7, FC9, FC10, FC14, FC15, FC16, FC17, FC19, FC20, FC23, FC24, FC25, FC26, FC27, FC28, FC33, FC36, FC39, FC41, FC46, FC47

*FC4 is mixed: it has a spec-omission component (spec doesn't prescribe who validates) AND a comprehension component (agent skips validation on PATCH, uses bare `except Exception`, omits financial input parsing). Classified as Tier 1a because the comprehension failures are real and actionable. See "Interpretation Boundaries" below for FC4-specific rules.

**Tier 1b: Spec-omission dominated (2 FCs)** -- testable in code output but real-world failures are driven by missing spec coverage surfaces, not unclear agent rules (see `docs/solutions/2026-05-21-spec-completeness-checker-pre-swarm-gate.md`):
FC1, FC35

**Tier 2: Multi-file or multi-agent context needed (16 FCs):**
FC3, FC5, FC6, FC18, FC21, FC22, FC29, FC30, FC31, FC32, FC38, FC40, FC42, FC43, FC44, FC45

**Tier 3: Requires real execution or tool-use eval (4 FCs):**
- FC8 -- tool-use behavior (bash command patterns), not code output. Needs a future tool-use eval mode.
- FC13 -- procedural (which DB path to use). Requires real filesystem context.
- FC34 -- filesystem concurrency (parallel run plan collision).
- FC37 -- real git (worktree agent commit verification).

**Tier 4: Orchestrator/process-level (2 FCs)** -- not agent code rules:
FC11, FC12

**V1 targets Tier 1a + Tier 1b (25 FCs), built in two stages:**
- **Stage 1:** 12 deterministic FCs (FC7, FC14, FC16, FC19, FC20, FC23, FC24, FC28, FC33, FC36, FC46, FC47). 12 x 5 x 2 x 3 = 360 agent calls, 0 judge calls. Cost: ~$0.40. No judge prompts needed.
- **Stage 2:** Add 13 FCs (11 hybrid/LLM-judge + 2 Tier 1b). 13 x 5 x 2 x 3 = 390 agent + 390 judge calls. Cost: ~$4-5. Requires judge prompts + calibration set.
- **Full run (both stages):** 25 FCs, 750 agent + 390 judge calls. Total cost: ~$5-6/run.
- **Gate:** Stage 2 starts only after Stage 1 produces a valid report.

### Interpretation Boundaries by FC Type

Simulation scores mean different things depending on FC type. The report must annotate each FC with its interpretation context.

**Tier 1a results (rule-clarity):**
- High pass (>95%) = rule is clear. No rewrite needed.
- Low pass (<70%) = rule is genuinely unclear. Priority rewrite.
- The with/without-rule delta measures how much the rule adds beyond the model's baseline knowledge.

**FC4 results (mixed -- Tier 1a with spec-omission component):**
- FC4 scenarios must target the **comprehension variants** (PATCH without Zod, bare `except Exception`, unvalidated financial parsing, same-status transition gaps) -- not the spec-ownership variant ("who validates?").
- High pass (>95%) = the comprehension variants of the rule are clear. **This is actionable** -- it means agent-level rule injection works for these failure modes, and remaining FC4 recurrence is spec-omission-driven.
- Low pass (<70%) = the rule is unclear even for comprehension variants. Priority rewrite.
- The spec-omission component (which agent owns validation?) is not measurable in focused mode. The spec-completeness-checker remains the gate for that component.
- Report annotation: `type: 1a-mixed` to signal that sim scores cover comprehension but not spec ownership.

**Tier 1b results (spec-omission dominated):**
- High pass (>95%) = **expected and not actionable.** The rule was always clear. This confirms that the spec, not the rule, is the real-world bottleneck.
- Low pass (<70%) = the rule is ALSO unclear, on top of the spec problem. Both need fixing. This is the only actionable Tier 1b finding.
- The with/without-rule delta is expected to be small for Tier 1b (the rules teach what the model already knows). A small delta is not a problem -- it confirms the spec-omission diagnosis.
- Tier 1b scores do NOT predict real-world recurrence. The spec-completeness-checker is the correct gate for these FCs.

**Report requirement:** Every FC row in the results table must include a `type` column (`1a`, `1a-mixed`, or `1b`) so the reader knows which interpretation applies.

### Evaluation Method Split (25 v1 FCs)

| Method | FCs | Count | Stage |
|--------|-----|-------|-------|
| Deterministic (regex/pattern) | FC7, FC14, FC16, FC19, FC20, FC23, FC24, FC28, FC33, FC36, FC46, FC47 | 12 | Stage 1 |
| LLM-as-judge | FC2, FC17, FC26 | 3 | Stage 2 |
| Hybrid (deterministic + LLM for edge cases) | FC1, FC4*, FC9, FC10, FC15, FC25, FC27, FC35, FC39, FC41 | 10 | Stage 2 |

### Model Split

- **Agent:** Haiku (~$0.001/call) -- cheap, fast, and represents the "most likely to fail" baseline
- **Judge:** Sonnet (~$0.01/call) -- better judgment, different model = reduces correlated blindspots
- **Calibration:** compare Haiku-agent results to Sonnet-agent on a subset to measure model sensitivity

### Scoring Buckets

- **CLEAR (>95% pass):** Rule is well-written. No action needed.
- **AMBIGUOUS (70-95%):** Rule is sometimes followed, sometimes not. Rewrite candidate.
- **BROKEN (<70%):** Rule is consistently misunderstood. Priority rewrite.

### Rule Delta Testing

Every FC gets tested both with-rule and without-rule. The delta measures the rule's actual impact. A high with-rule score but also-high without-rule score means the rule is teaching something the model already knows -- lower priority for injection.

## Architecture (Conceptual)

```
agent-pitfalls.md
       |
   [FC Parser] --> List[FailureClass]  (Pydantic models)
       |
   [Scenario Bank] --> Dict[FC_ID, List[Scenario]]  (hand-written YAML per FC)
       |
   [Runner]
       |--- builds agent prompt (brief + scenario + optional rule)
       |--- calls Anthropic API (Haiku)
       |--- gets code output
       |
   [Evaluator]
       |--- deterministic checks (regex patterns per FC)
       |--- LLM judge (Sonnet, structured output)
       |--- produces EvalResult(verdict, evidence, confidence, fc_id)
       |
   [Scorer]
       |--- aggregates per-FC
       |--- computes pass rate, variance, delta (with/without rule)
       |--- flags AMBIGUOUS and BROKEN
       |
   [Reporter]
       |--- markdown summary (per-rule table, ambiguity flags, promotable cases)
       |--- JSON data (for future build recommender consumption)
```

## V1 Success Criteria

### Outputs
1. Per-rule adherence score (pass rate across N scenarios)
2. Ambiguity report (rules in the 70-95% band)
3. Rule clarity ranking (all tested FCs, most to least reliable)
4. With/without-rule delta per FC
5. Promotable cases (scenario+output pairs where rules consistently fail)

### Metrics
- Per-rule pass rate target: >90% for well-written rules
- Inter-scenario variance: low variance = clear rule, high variance = ambiguous
- Judge-human agreement on pilot sample: >85%
- Calibration set accuracy: >90% (20 hand-labeled cases, run every batch)

### Promotion Criteria (manual, strong-evidence only)
A scenario is a promotion candidate when it demonstrates a **reproducible failure with strong evidence**, not an ambiguous one. The report surfaces the strongest candidates at the top, ranked by reproduction rate and evidence quality.

Promotion evidence tiers (any one is sufficient):
1. **Deterministic failure:** The deterministic check detects the violation pattern in 2+ out of 3 runs (for deterministic/hybrid check types). Strongest evidence -- no judge interpretation involved.
2. **High-confidence judge failure:** The LLM judge returns FAIL with confidence >= 0.8 in 2+ out of 3 runs (for LLM-judge check types). Strong evidence -- consistent, confident verdict.
3. **Human-confirmed failure:** A borderline case (judge confidence 0.5-0.8, or 1-of-3 reproduction) that a human reviewer confirmed as a real violation during the calibration review sample.

Promotion remains manual. Low-confidence or split verdicts are flagged as "needs human review," not promoted.

## Calibration Strategy

1. Build 20-case calibration set: 10 clear violations + 10 clear passes, hand-labeled
2. Run judge against calibration before every batch. Accuracy < 90% = stop and fix judge prompt.
3. Pilot: review 100% of first run (3 FCs x 5 scenarios = 15 cases)
4. Ongoing: review all FAIL verdicts with confidence < 0.8
5. Include calibration set in every batch to detect drift

## Minimum Components (v1)

**Stage 1 (pipeline validation -- 12 deterministic FCs):**
1. **FC Parser** -- extracts structured data from `agent-pitfalls.md` (Pydantic models)
2. **Scenario Bank** -- 5 unique scenarios per FC, each with with/without-rule variant (YAML files)
3. **Agent Runner** -- Anthropic API, Haiku, returns generated code
4. **Deterministic Checks** -- regex/pattern matchers for 12 FCs
5. **Scorer + Reporter** -- aggregation, markdown/JSON output
6. **CLI** -- `python pitfall_eval.py --fc fc7 --runs 5` or `--stage 1 --runs 3`

**Stage 2 (full coverage -- adds 13 FCs):**
7. **Judge** -- Anthropic API, Sonnet, structured output (verdict, evidence, confidence)
8. **Per-FC Judge Prompts** -- 13 judge prompt files (hybrid + LLM-judge FCs)
9. **Calibration Set** -- 20 hand-labeled cases for judge validation

## Out of Scope (v1)

- Build recommender
- Real tool execution (no filesystem, no git, no Docker)
- Multi-agent interaction simulation
- Automated rule rewriting suggestions
- Web dashboard
- Adversarial scenario auto-generation
- Integration with autopilot pipeline
- Tier 2/3 FC scenarios

## Roadmap

### V1: Pitfall Rule Smoke Tester (two stages)
- **Stage 1:** 12 deterministic FCs, hand-written scenarios, CLI, ~$0.40/run. Validates pipeline end-to-end.
- **Stage 2:** Add 13 hybrid/LLM-judge/Tier 1b FCs (25 total), judge prompts, calibration set. ~$5-6/full run.
- **Gate:** Stage 1 must produce a valid report before Stage 2 begins.

### V2: Depth + History (if v1 validates)
- LLM-generated adversarial scenarios (5 -> 50 per FC)
- Tier 2 FC support (multi-file scenario templates)
- Historical correlation (compare sim scores to real build FC hit rates)
- "Cognitive load" mode (rule buried among 15 others, full feature brief)
- Regression suite: promoted cases run before each real build

### V3: Build Recommender
- Consumes v1 adherence data + v2 historical correlation
- Inputs: AMBIGUOUS FCs + recurrence data + time-since-last-test
- Output: recommended next build shape (agent count, stack, features to include)

## Critical Challenge

**Most likely way this is wrong:** The harness tests "Can Claude identify the right pattern when the rule is in front of it?" but real failures happen because the rule is one of 47 competing for attention while the agent builds a feature. The real failure mode is attention/salience, not comprehension. If rules are already clear (most are), the harness shows 95%+ and tells you nothing actionable.

**Mitigation:** The with/without-rule delta partially addresses this. If a rule scores 95% with-rule and 90% without-rule, the rule adds 5% -- low impact. If it scores 95% with and 40% without, the rule is genuinely load-bearing. The "cognitive load" variant (v2) is the real test.

**Hidden assumptions:**
1. Rule clarity is the bottleneck for Tier 1a FCs. For Tier 1b FCs (FC1, FC35), it provably is NOT -- spec omissions drive those failures. FC4 is mixed (comprehension + spec-omission). The harness separates these with different interpretation rules, but the risk remains that more Tier 1a FCs are actually spec-omission-dominated than currently classified.
2. Synthetic scenarios represent real diversity. Hand-writing 5 per FC captures known patterns, misses unknown variants.
3. Haiku-agent behavior generalizes to Opus-agent behavior. Haiku may fail rules that Opus follows easily.
4. Scenario authoring effort is manageable. Stage 1 needs 60 scenarios (12 FCs x 5) to produce first useful results. Stage 2 adds 65 more (13 FCs x 5). Total: 125 unique scenarios. Staging means the harness produces useful results after ~15 hours of writing, not ~27.

## Do This / Don't Do This

| Do | Don't |
|----|-------|
| Start with 12 deterministic FCs (Stage 1), then expand to 25 (Stage 2) | Try to cover all 47 or skip pipeline validation |
| Hand-write 5 unique scenarios per FC (10 runs with variants) | Auto-generate before validating harness works |
| Use deterministic checks where regex works | Use LLM judge for everything |
| Include calibration set in every run | Trust judge without baseline |
| Measure with-rule vs without-rule delta | Only measure with-rule pass rate |
| Report what the harness CANNOT test (Tier 3) | Imply full coverage |
| Manual promotion of regression cases | Auto-promote into test suites |
| Run Haiku as agent, Sonnet as judge | Same model for both |
| One Python package, flat structure | Microservices or complex abstractions |

## Project Location

`eval-harness/` at sandbox root, self-contained:

```
eval-harness/
  pitfall_eval.py          # CLI entry point
  parser.py                # FC parser (agent-pitfalls.md -> Pydantic models)
  runner.py                # Agent API caller
  judge.py                 # Judge API caller + deterministic checks
  scorer.py                # Aggregation + scoring
  reporter.py              # Markdown/JSON output
  models.py                # Pydantic models (Scenario, EvalResult, etc.)
  scenarios/
    fc1-naming-divergence.yaml
    fc2-wrong-usage-inferred.yaml
    ...
    fixtures/              # Large code blocks referenced by scenarios
      fc1-naming-spec-a.py
      fc27-existing-routes.py
      ...
  judges/
    fc1-naming-divergence.txt   # Per-FC judge prompt
    fc4-validation-gap.txt
    ...
    base-judge.txt              # Universal base (shared preamble)
  calibration/
    calibration-set.yaml        # 20 hand-labeled cases
  reports/                      # Generated output
    2026-05-23-tier1-run.md
    2026-05-23-tier1-run.json
```

## Scenario Format Design

### Why YAML-per-FC

1. **Reviewability.** Each file is 50-150 lines covering one failure class. PRs that add scenarios are easy to review -- you see exactly which FC is being expanded.
2. **Hand-writing optimized.** YAML's multiline strings (`|`) are natural for code blocks and task briefs. JSON requires escaping every newline.
3. **Independent editing.** Two people (or agents) can add scenarios to different FCs without merge conflicts.
4. **Tier 2 ready.** The `context_files` field (see schema below) supports multi-file scenarios without redesigning the format. Tier 2 adds fixture files; the YAML structure doesn't change.

### Scenario Schema (Pydantic-validated)

```yaml
# scenarios/fc7-route-prefix-doubling.yaml
fc_id: fc7
fc_slug: route-prefix-doubling
scenarios:
  - id: fc7-flask-categories-basic
    title: "Flask blueprint with /categories prefix"
    stack: flask
    task_brief: |
      Create a Flask blueprint for categories.
      The blueprint is registered with url_prefix="/categories".
      Add a route that lists all categories and a route for a single category.
    inputs:
      blueprint_prefix: "/categories"
      existing_code: null
    context_files: []           # empty for Tier 1, populated for Tier 2
    expected_check_type: deterministic  # deterministic | llm_judge | hybrid
    expected_outcome: pass      # pass | fail (what a correct agent should produce)
    deterministic_pattern: '/categories/categories/'  # grep pattern for violation
    deterministic_mode: absence  # presence | absence (absence = pattern must NOT appear)
    tags: [flask, blueprint, routing]
    pair_group: fc7-flask-basic  # groups with/without-rule variants
    variant: with_rule           # with_rule | without_rule | adversarial

  - id: fc7-flask-categories-basic-norule
    title: "Flask blueprint with /categories prefix (no rule injected)"
    stack: flask
    task_brief: |
      Create a Flask blueprint for categories.
      The blueprint is registered with url_prefix="/categories".
      Add a route that lists all categories and a route for a single category.
    inputs:
      blueprint_prefix: "/categories"
      existing_code: null
    context_files: []
    expected_check_type: deterministic
    expected_outcome: unknown     # we don't know if it passes without the rule
    deterministic_pattern: '/categories/categories/'
    deterministic_mode: absence
    tags: [flask, blueprint, routing]
    pair_group: fc7-flask-basic
    variant: without_rule

  - id: fc7-express-api-nested
    title: "Express router with /api/v1 prefix and nested routes"
    stack: express
    task_brief: |
      Create an Express router for user management.
      The router is mounted at app.use('/api/v1/users', router).
      Add routes for GET /, GET /:id, POST /, and DELETE /:id.
    inputs:
      router_mount: "/api/v1/users"
      existing_code: null
    context_files: []
    expected_check_type: deterministic
    expected_outcome: pass
    deterministic_pattern: '/api/v1/users/api/'
    deterministic_mode: absence
    tags: [express, router, routing]
    pair_group: fc7-express-nested
    variant: with_rule
```

### Pydantic Model

```python
class Scenario(BaseModel):
    id: str                          # unique, kebab-case: fc7-flask-categories-basic
    title: str                       # human-readable, <80 chars
    stack: Literal["flask", "express", "nextjs", "supabase", "sqlite", "generic"]
    task_brief: str                  # the prompt given to the agent
    inputs: dict[str, Any]           # structured inputs (prefix, existing code, etc.)
    context_files: list[str]         # relative paths to fixtures/ (empty for Tier 1)
    expected_check_type: Literal["deterministic", "llm_judge", "hybrid"]
    expected_outcome: Literal["pass", "fail", "unknown"]
    deterministic_pattern: str | None = None   # required if check_type includes deterministic
    deterministic_mode: Literal["presence", "absence"] | None = None
    tags: list[str]
    pair_group: str | None = None    # groups with/without-rule variants
    variant: Literal["with_rule", "without_rule", "adversarial"] = "with_rule"

class ScenarioFile(BaseModel):
    fc_id: str                       # must match a parsed FC ID
    fc_slug: str                     # must match the FC's slug
    scenarios: list[Scenario]

    @model_validator(mode="after")
    def validate_ids_match_fc(self) -> Self:
        for s in self.scenarios:
            if not s.id.startswith(self.fc_id):
                raise ValueError(f"Scenario {s.id} must start with {self.fc_id}")
        return self

    @model_validator(mode="after")
    def validate_deterministic_fields(self) -> Self:
        for s in self.scenarios:
            if s.expected_check_type in ("deterministic", "hybrid"):
                if not s.deterministic_pattern:
                    raise ValueError(f"Scenario {s.id} needs deterministic_pattern")
                if not s.deterministic_mode:
                    raise ValueError(f"Scenario {s.id} needs deterministic_mode")
        return self

    @model_validator(mode="after")
    def validate_pair_groups_complete(self) -> Self:
        groups: dict[str, set[str]] = {}
        for s in self.scenarios:
            if s.pair_group:
                groups.setdefault(s.pair_group, set()).add(s.variant)
        for group, variants in groups.items():
            if "with_rule" not in variants:
                raise ValueError(f"Pair group {group} missing with_rule variant")
            if "without_rule" not in variants:
                raise ValueError(f"Pair group {group} missing without_rule variant")
        return self
```

### Validation Rules

1. **Schema validation:** Every YAML file is loaded into `ScenarioFile` at startup. Invalid files crash immediately with a clear error -- no partial loading.
2. **ID uniqueness:** All scenario IDs across all files must be globally unique. Checked at load time.
3. **FC cross-reference:** `fc_id` must match a failure class extracted by the parser. Orphan scenarios are errors.
4. **Fixture existence:** Every path in `context_files` must exist in `scenarios/fixtures/`. Missing fixtures are errors.
5. **Pair group completeness:** Every `pair_group` must have both `with_rule` and `without_rule` variants.
6. **Deterministic field consistency:** If `expected_check_type` is `deterministic` or `hybrid`, `deterministic_pattern` and `deterministic_mode` are required.

### Tier 2 Compatibility

The `context_files` field is the bridge. For Tier 1, it's always empty -- the scenario is self-contained in `task_brief`. For Tier 2 (FC3, FC5, FC29, etc.), context_files references fixture files that represent "Agent A already wrote this code":

```yaml
# Tier 2 example (future)
- id: fc29-flask-payment-flow
  title: "Multi-function payment flow with premature commit"
  stack: flask
  task_brief: |
    You are implementing update_payment_status(). Another agent already wrote
    create_checkout_link() in checkout.py. Your function will be called as part
    of a larger flow: update_status -> create_checkout_link -> store_order_id.
    Do NOT add conn.commit() inside your function.
  inputs:
    caller_file: "routes/payments.py"
  context_files:
    - fc29-checkout-module.py        # "Agent A's" code
    - fc29-payment-routes-stub.py    # the file the agent will modify
  expected_check_type: hybrid
  expected_outcome: pass
  ...
```

No format redesign needed. The fixture files are plain Python/JS/TS files that the runner includes in the agent's context alongside the task_brief.

### Format Risks and Containment

| Risk | Containment |
|------|-------------|
| YAML multiline strings get messy for large code blocks | `context_files` references external fixture files. Rule: if code > 20 lines, use a fixture. |
| Scenario count grows unwieldy per file | Cap at 20 scenarios per YAML file. Split into `fc1-naming-divergence-flask.yaml` and `fc1-naming-divergence-express.yaml` if needed. |
| Schema evolves and breaks old scenarios | Version field in frontmatter. Pydantic model handles migrations explicitly. |
| Pair group tracking becomes complex | Validator enforces completeness. Scorer groups by pair_group automatically. |

## Agent Prompt Design

### Prompt Modes

V1 implements one mode. The architecture supports adding more via a `prompt_mode` field recorded in every result.

| Mode | What it tests | V1? | When to add |
|------|--------------|-----|-------------|
| `focused` | Rule comprehension/clarity in controlled conditions | Yes | V1 |
| `swarm_realistic` | Rule salience/attention under cognitive load (15+ rules, file ownership, role context) | No | V2, first extension if v1 works |

**V1 measures rule comprehension, not swarm performance.** If a rule scores poorly in focused mode, it is genuinely unclear. If it scores well in focused mode but fails in real builds, the problem is salience, not clarity -- and that's what `swarm_realistic` mode is for.

### `focused` Mode Template

```
System: You are a senior {stack} developer.
Complete the task below. Follow the rules provided.

Rules:
{rule_text}

Task:
{task_brief}

{context_files_content if any}

Respond with ONLY the code. No explanations.
```

Requirements:
- Stable system prompt with role and coding context
- Task brief from the scenario YAML
- Rule text for the target FC (omitted in `without_rule` variants)
- Minimal surrounding context -- only what the task requires
- Clear output contract ("Respond with ONLY the code") so the judge inspects consistent output

What the focused prompt does NOT include:
- File ownership constraints
- Other agents' rules or pitfalls
- Orchestration detail (BUILD_TRACKING, checkpoint gates)
- Multiple unrelated rules

### Report Caveat (mandatory on every report)

> These results estimate rule clarity/comprehension under controlled prompting. They do not estimate adherence under realistic swarm cognitive load.

### `swarm_realistic` Mode (v2 design note)

When added, this mode would:
- Include the target rule among 10-15 other FC rules
- Add file ownership constraints ("you own routes/categories.py only")
- Add swarm role context ("you are Agent 4 of 12")
- Test whether the agent still follows the target rule when it's buried in noise

This directly tests the Feed-Forward risk: that real failures are attention problems, not clarity problems.

## Judge Prompt Strategy

**Per-FC judge prompts** stored in `judges/fc{N}-{slug}.txt`. Each knows the specific violation pattern.

Structure:
- `judges/base-judge.txt` -- shared preamble (output format, confidence scale, evidence requirements)
- `judges/fc7-route-prefix-doubling.txt` -- FC-specific: what the violation looks like, what correct code looks like, common false positives

The runner concatenates: base prompt + FC-specific prompt + the agent's output + the rule text.

**Why per-FC, not universal:**
- FC7 (route prefix doubling) has a very different violation shape than FC26 (comment-not-code). A universal prompt would need to be so general that it catches neither well.
- Per-FC prompts can include specific false positive examples ("a route that starts with /cat is NOT a doubled prefix of /categories").
- Cost is low: 25 text files, each ~20-50 lines, written once alongside the scenarios.

## Planning Requirements

The plan phase must include:
- **EARS-format acceptance tests** for both stages (e.g., "WHEN the harness runs Stage 1 with 12 deterministic FCs THE SYSTEM SHALL produce a JSON report with per-FC pass rates"). Not elaborated here -- this is a plan deliverable, not a brainstorm deliverable.

## Resolved Questions

- **Primary goal?** Rule quality testing. Build recommender is v2/v3.
- **Adversarial mode?** A test mode within the harness, not the product definition.
- **Platform scope?** CLI tool, not a platform.
- **Scenario format?** YAML-per-FC, Pydantic-validated at load time. Strict schema, no free-form blobs.
- **Project location?** `eval-harness/` at sandbox root, self-contained.
- **Judge strategy?** Per-FC judge prompts with shared base preamble.
- **Tier 2 compatibility?** `context_files` field + `fixtures/` directory. Format doesn't change, just adds referenced files.
- **Agent prompt mode?** `focused` only in v1 (tests rule comprehension). `swarm_realistic` is v2 (tests salience under load). Reports always record which mode was used.

## Feed-Forward

- **Hardest decision:** How to classify FC4. It has both a spec-omission component (who owns validation?) and a comprehension component (PATCH without Zod, bare `except Exception`). Moved it to Tier 1a with a `1a-mixed` annotation so simulation scores are treated as actionable, while acknowledging the spec-omission component is not covered.
- **Rejected alternatives:** (1) Keeping FC4 as pure Tier 1b -- this would mark a high sim pass as "not actionable," hiding real comprehension failures. (2) Splitting FC4 into FC4a/FC4b sub-variants -- adds taxonomy complexity without proportional value; the `1a-mixed` annotation achieves the same goal. (3) Building all 25 FCs before validating the pipeline -- risks 27 hours of scenario authoring on a harness that might not work. Staged build (12 deterministic first) de-risks this. (4) Keeping FC8 in v1 -- tool-use behavior, not code output. Dropped.
- **Least confident:** Whether focused-mode simulation produces actionable signal for enough FCs to justify the effort. Real-world failures have three distinct causes, and v1 only measures one:
  1. **Clarity/comprehension** (Tier 1a) -- the rule is unclear. V1 measures this directly.
  2. **Salience/attention under load** (all tiers in real builds) -- the rule is clear but buried among 46 others. V2 `swarm_realistic` mode needed.
  3. **Spec-coverage omissions** (Tier 1b) -- the rule is clear and salient, but the spec doesn't provide the data the rule needs. Spec-completeness-checker covers this.
  If most Tier 1a FCs score >95% (rules are already clear), the harness confirms clarity but doesn't explain why those FCs still recur in builds. The delta test and the `1a-mixed` annotation on FC4 help, but the v2 cognitive load mode is where the real diagnostic power lies.
