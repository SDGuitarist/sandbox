# Spec Eval Gate Brainstorm

**Date:** 2026-05-24
**Status:** Complete
**Next:** `/workflows:plan`

## What We're Building

A pre-swarm gate (step 9w.8) that tests whether agents can follow a spec's concrete instructions before launching a swarm build. It auto-extracts testable claims from spec prose and tables, generates scenarios, runs them through the eval harness runner and judge (reusing runner.py + judge.py, with its own scoring logic), and blocks the swarm if agents can't reliably follow the spec.

### The Question This Gate Answers

**"Given this spec's exact claims, does an agent produce code that matches those claims?"**

This is distinct from the two existing gates:

| Gate | Question |
|------|----------|
| Spec Completeness (9w.6) | Did the spec mention the needed things? |
| **Spec Eval Gate (9w.8)** | **Can an agent execute this spec's concrete claims?** |
| Pitfall Eval + MC | Given relevant FC risk, what is the projected build cleanliness? |

### Interpretation

- **PASS** = the spec's concrete instructions are precise enough for an agent to follow
- **FAIL** = the spec is ambiguous, underspecified, or phrased in a way agents misapply
- **WARN-UNSCORABLE** = too few high-confidence claims were extracted; spec may not be structured enough to evaluate

## Why This Approach

### Prior Lessons Applied

1. **spec-completeness-checker (2026-05-21):** Spec-first validation catches P1s that agent rules can't. The Spec Eval Gate extends this from structural checks ("does the section exist?") to behavioral checks ("can an agent follow what it says?").
2. **autonomy-hardening (2026-05-13):** Enforcement belongs in the engine, not prose. All claims must be machine-verifiable (deterministic checks preferred, LLM judge only when necessary).
3. **spec-convergence-loop (2026-04-30):** P0s are cross-section contradictions. The extraction phase must pull claims from multiple sections and test them independently, not treat each section as self-contained.

### Prior Risk Addressed

The HANDOFF Feed-Forward flagged: "The 100% MC projection assumes all with_rule pass rates are truly 100%." The Spec Eval Gate adds a different signal -- spec-specific adherence -- that catches failures the generic MC model cannot predict (ambiguous instructions that are unique to each spec).

## Key Decisions

### 1. Extraction Strategy: Tables + Targeted Prose

**Hybrid extraction** optimizing for precision over recall:

- **Phase 1 (deterministic):** Parse structured tables into candidate claims
  - Export Names table -> name presence checks
  - Input Validation prescriptions -> regex for validators
  - Authorization Matrix -> role/permission check patterns
  - Route/endpoint tables -> path and method checks
  - Schema/model tables -> field presence checks

- **Phase 2 (targeted LLM):** Sonnet reads prose sections, extracts only atomic testable claims
  - Coordinated Behaviors -> concrete wiring relationships
  - Sequencing requirements -> import/dependency ordering
  - Validation rules stated in prose -> specific validation patterns

**Extractability rule:** A prose sentence is extractable only if it decomposes into:

```
instruction_type:    (naming | validation | wiring | auth | sequencing | schema)
subject:             (the entity being constrained)
required_behavior:   (what must happen)
evidence_to_check:   (what to look for in code output)
```

Examples:
- "validate email before save" -> YES (validation, email field, check before insert, regex/validator present)
- "the UX should feel clean" -> NO (no concrete evidence to check)
- "agent-2 owns route function list_tasks" -> YES (naming, list_tasks, defined by agent-2, function name presence)
- "workers should coordinate carefully" -> NO (no specific behavior or evidence)

**Claims that don't decompose cleanly are rejected, not forced into scenarios.**

Both table-extracted and prose-extracted claims should produce a unified `Claim` structure (the 4-tuple above plus a `source` field indicating table vs. prose and a `confidence` score). Exact schema is a plan-phase decision.

### 2. Model Split: Sonnet Extracts, Haiku Tests

- **Sonnet** reads the spec and produces atomic, testable claims as scenario YAML. Extraction is the highest-leverage failure point -- a weak extractor makes the gate look cleaner than reality by missing hard instructions.
- **Haiku** runs the scenarios (existing harness runner). Testing should use the weaker model to prove the spec is followable by the actual build agents.
- **Deterministic checks** first. Sonnet judge calls only for claims where no regex pattern exists.

**Principle:** Use the stronger model to understand the spec. Use the weaker model to prove the spec is followable.

### 3. Confidence-Filtered 100% Threshold

Gate output buckets:
1. **PASSING claims** -- high-confidence, tested, passed
2. **FAILING claims** -- high-confidence, tested, failed (blocks swarm)
3. **UNTESTED / LOW-CONFIDENCE claims** -- reported as warnings, do not block

**Gate rule:**
- **PASS** only if ALL high-confidence testable claims pass
- **FAIL** if ANY high-confidence testable claim fails
- **WARN-UNSCORABLE** if fewer than 3 high-confidence claims are extracted from a spec that should be testable (prevents empty-pass from bad extraction; exact threshold is a plan-phase decision)

**Principle:** Require perfection on trusted claims. Explicitly surface untrusted claims instead of averaging them away.

### 4. Hard FAIL, Human Fixes

When the gate fails:
1. Block the swarm
2. Emit a structured failure report:
   - Failed claim
   - Expected spec instruction
   - Observed agent behavior
   - Likely failure type (naming ambiguity, underspecified validation, unclear auth rule, missing wiring detail)
   - Suggested human fix direction
3. Human edits the spec
4. Re-run the gate

**No auto-rewrite.** The gate judges spec clarity, not agent capability. Auto-rewriting would silently change the contract before the swarm runs, collapsing evaluation and authoring into one step. Debugging becomes impossible when the failing input is no longer the input that reaches the swarm.

**Possible v2:** Allow narrow auto-fix suggestions for mechanical issues (casing normalization), but require human acceptance before mutating the spec.

### 5. Pipeline Placement: Step 9w.8

```
9w.5  Spec Consistency Gate      (does the spec contradict itself?)
9w.6  Spec Completeness Gate     (did the spec cover required surfaces?)
9w.7  Gate Verification          (did earlier gates run and produce artifacts?)
9w.8  Spec Eval Gate [NEW]       (can an agent follow this spec's instructions?)
10w   Swarm Launch
```

- Spec Eval Gate is a new semantic gate; verification remains the meta-check layer
- **Ordering note:** 9w.7 currently verifies 9w.5 + 9w.6 artifacts. Since 9w.8 runs after 9w.7, the Spec Eval Gate must be self-gating (its own PASS/FAIL blocks the swarm directly). The plan should decide whether to move 9w.7 verification to run last (after all gates) or keep 9w.8 as an independent blocker that doesn't need verification to check it.

### 6. Cost and Speed Budget

| Component | Model | Estimated Cost |
|-----------|-------|---------------|
| Extractor | Sonnet | ~$0.04 |
| Runner | Haiku (15 scenarios x 1 run) | ~$0.05 |
| Judge | Deterministic (free) + 2-3 Sonnet calls | ~$0.03 |
| **Total** | | **~$0.12** |

- Well under $1 ceiling
- Estimated runtime: ~2 minutes (15 scenarios, 1 run each, sequential)
- Budget headroom allows scaling to ~50 scenarios before hitting $1

## Data Flow

```
Spec document (prose + tables)
       |
  [Sonnet extractor]
       |
  List[Claim] with confidence scores
       |
  [Scenario generator] -- maps claims to scenario YAML
       |
  scenarios/spec-eval-<run-id>.yaml
       |
  [Existing harness: runner.py + judge.py]  (reuse runner + judge only)
       |
  EvalResults per claim
       |
  [Gate scorer] -- NEW, not existing scorer.py
       |                (no delta/pair scoring -- just pass/fail per claim
       |                 with confidence-filtered 100% threshold)
       |
  spec-eval-gate.md report
       |
  PASS -> proceed to 10w
  FAIL -> block, human fixes spec
  WARN-UNSCORABLE -> block, spec needs more structure
```

**Harness reuse note:** The existing harness expects paired with_rule/without_rule scenarios with delta scoring. Spec-eval scenarios don't have natural pairs -- they test "can the agent follow this instruction?" not "does the rule improve output?" The plan must decide whether to:
- (a) Skip pairing entirely -- single-variant scenarios with pass/fail only (simplest)
- (b) Define "without_rule" as "same task without spec instruction" to measure whether the spec adds clarity beyond baseline
- (c) Add a new variant type (e.g., `spec_adherence`) to the Scenario model

Option (a) means the gate uses runner.py + judge.py but NOT scorer.py. The gate scorer is new code with different logic (confidence-filtered 100% threshold, no Wilson CI, no delta).

## Output Artifact

```
docs/reports/<run-id>/spec-eval-gate.md

SPEC EVAL GATE: PASS | FAIL | WARN-UNSCORABLE

Claims extracted: N
  HIGH confidence: X (from tables + strong prose)
  LOW confidence:  Y (from weak prose)

HIGH-CONFIDENCE RESULTS:
  PASSED: X/X
  FAILED: 0

  [If FAIL, per-claim detail:]
  claim_07: Export name mismatch
    Spec:     list_tasks
    Agent:    listTasks
    Type:     naming ambiguity
    Fix hint: Add explicit casing convention to spec

LOW-CONFIDENCE WARNINGS:
  claim_10: coordination rule unclear
  claim_12: sequencing claim may be over-interpreted

Cost:    $0.12
Runtime: 1m 47s
```

## Open Questions

_All resolved during brainstorm dialogue._

## Resolved Questions

1. **What does the gate test?** Spec-adherence -- can an agent follow this spec's exact claims? (Not generic FC rules, not structural completeness.)
2. **Extraction strategy?** Tables + targeted prose. Precision over recall. Only atomic testable claims.
3. **Which models?** Sonnet extracts, Haiku tests. Stronger model understands, weaker model proves.
4. **Threshold?** 100% of high-confidence claims must pass. Low-confidence claims are warnings. Minimum extraction threshold prevents empty-pass.
5. **Fail behavior?** Hard FAIL, block swarm, structured report, human fixes spec. No auto-rewrite.
6. **Pipeline placement?** New step 9w.8 after verification. Update 9w.7 to know about 9w.8.

## V2 Possibilities (Not in Scope)

- Auto-fix suggestions for mechanical issues (casing normalization), with human acceptance gate
- FC-relevance filtering as a second pass (compose with existing MC simulator)
- Calibration set for LLM-judge extracted claims
- Cross-spec regression testing (run gate across multiple past specs to validate extractor quality)

## Feed-Forward

- **Hardest decision:** Extraction strategy -- tables-only would be simpler and cheaper, but misses behavioral/validation claims that are the most common source of spec-adherence failures. Targeted prose extraction adds complexity and LLM cost but catches the claims that matter most.
- **Rejected alternatives:** (1) Auto-rewrite on fail -- collapses evaluation and authoring, makes debugging impossible. (2) Percentage threshold -- waters down the gate by letting known-ambiguous claims reach the swarm. (3) LLM extracts all sections -- too noisy and expensive for v1.
- **Least confident:** Two uncertainties, both untested. (1) Quality of LLM-extracted prose claims -- Sonnet may over-extract (producing scenarios from vague prose) or under-extract (missing concrete claims buried in paragraphs). The extractability rule (instruction_type, subject, required_behavior, evidence_to_check) is the best heuristic we have, but it's untested against real specs. (2) Harness reuse -- the existing Scenario model expects paired variants and delta scoring, which spec-eval scenarios don't need. The plan must decide how much model adaptation is required vs. building a simpler single-variant path.
