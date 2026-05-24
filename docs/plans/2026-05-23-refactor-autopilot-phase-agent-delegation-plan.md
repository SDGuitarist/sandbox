---
title: "refactor: Autopilot Phase Agent Delegation"
type: refactor
status: active
date: 2026-05-23
origin: docs/brainstorms/2026-05-23-autopilot-agent-delegation-brainstorm.md
swarm: false
feed_forward:
  risk: "Whether compound can eventually be split from review+resolve (Bundle 4). Currently V1 non-negotiable bundle -- not empirically tested."
  verify_first: true
---

# refactor: Autopilot Phase Agent Delegation

## Overview

Refactor the autopilot pipeline so each major phase runs in its own spawned
agent with its own context window. The orchestrator becomes a thin dispatcher
that reads deterministic on-disk YAML manifests between phases. This reduces
orchestrator context from ~80-150k tokens to ~15-20k, eliminating the need
for /tail-resume checkpoint recovery in most builds.

## Problem Statement

The autopilot orchestrator runs every phase (brainstorm, plan, deepen,
doc-review, work, review, resolve, compound) inline in a single session.
Each phase adds 5-40k tokens. By the shared tail (learnings, self-audit),
context is exhausted. The existing checkpoint gate (load > 30) is a band-aid
that requires manual /tail-resume in a new session.

Root cause: the orchestrator accumulates full phase output in its context
window even though phases already write artifacts to disk.

## Proposed Solution

Delegate phases to spawned agents organized into 5 bundles based on coupling
analysis (see brainstorm: docs/brainstorms/2026-05-23-autopilot-agent-delegation-brainstorm.md,
Key Decision 1). Each bundle agent writes a YAML manifest to a deterministic
path. The orchestrator reads manifests for state, never depending on agent
return values.

## Enhancement Summary

**Deepened on:** 2026-05-23
**Agents used:** 7 (agent-native-architecture, create-agent-skills, orchestrating-swarms, architecture-strategist, pattern-recognition-specialist, code-simplicity-reviewer, agent-native-reviewer)

### Key Improvements

1. **Non-Interactive Encoding Contract** -- Phase agents MUST NOT invoke /workflows:* skills. All logic is re-implemented inline. (3 agents flagged ambiguity)
2. **Simplified manifest schema** -- Removed 8 YAGNI fields (timestamps, branch names, commits, deterministic paths). Added `failure_reason` and `manifest_version`. Flattened to single-line values only.
3. **Stale manifest cleanup** -- Orchestrator deletes Bundle 1-2 manifests at pipeline start. (3 agents flagged collision risk)
4. **Tool allocation tightened** -- Removed `Agent` from phase-plan and phase-work (3 agents agreed on least-privilege). Added spaces after commas in tool lists.
5. **Agent body structure standardized** -- Use `## Role`, `## Inputs`, `## Injected Context`, `## Rules`, `## Output Contract` (5-section pattern extending existing agents with orchestrator-provided context). Source workflow version moved to frontmatter.
6. **Context injection template** -- Structured `## Injected Context` section in each agent prompt with named placeholder fields.
7. **Persist expanded brief to disk** -- Step 2 writes brief to `docs/reports/expanded-brief.md` so all phase agents can read it.
8. **Bundle 4 strictly monolithic in V1** -- Compound split experiment deferred to follow-up plan. Prompt size cap enforced via companion reference file if needed.
9. **Prompt size calibration moved** -- Test on Bundle 2 or 3 (largest prompts), not Bundle 1 (simplest).
10. **Recovery point semantics specified** -- `git reset --hard <recovery_point>` to discard partial commits; disk artifacts outside git (deepen-raw/, manifest sentinel) survive for recovery shortcuts.

### Simplification Tension (Noted)

The code-simplicity reviewer recommended collapsing 6 implementation phases to 2 and dropping per-bundle side-by-side validation. This conflicts with the user's explicit brainstorm decision (acceptance criteria + one-time side-by-side per bundle). The current plan keeps the user's chosen validation strategy but notes the simplification option as a V2 consideration if the phased rollout proves unnecessarily cautious.

## Technical Approach

### Architecture

```
BEFORE (single context):
  orchestrator runs brainstorm (5-8k) + plan (8-12k) + deepen (10-15k)
  + doc-review x2 (6-10k) + work (20-40k) + review (15-25k) + resolve
  (5-10k) + compound (5-8k) + tail (10k) = 80-150k+ tokens

AFTER (dispatcher + agents):
  orchestrator: setup (5k) + manifest reads (1.5k) + coordination (1k)
  + swarm inline (varies) + tail (10k) = 15-20k tokens
  each phase agent: gets full context window for its own work
```

### File Changes

| File | Action | Purpose |
|------|--------|---------|
| `.claude/agents/phase-brainstorm.md` | CREATE | Bundle 1 agent |
| `.claude/agents/phase-plan.md` | CREATE | Bundle 2 agent |
| `.claude/agents/phase-deepen.md` | CREATE | Bundle 3 agent |
| `.claude/agents/phase-review.md` | CREATE | Bundle 4 agent |
| `.claude/agents/phase-work.md` | CREATE | Solo work agent |
| `.claude/skills/autopilot/SKILL.md` | MODIFY | Rewrite to dispatcher |

### Implementation Phases

#### Phase 1: Manifest Schema + Bundle 1 (Brainstorm + Refinement)

**Goal:** Validate the phase-agent harness end-to-end.

**1a. Define the manifest schema**

Create a reference manifest schema that all phase agents follow. This is
not a separate file -- it's the contract documented in this plan and
encoded in each phase agent's instructions.

### Research Insights: Manifest Schema

**Simplification (code-simplicity-reviewer):** The original schema had 20+ fields.
8 were YAGNI -- no downstream consumer reads them. Removed: `started_at`,
`completed_at`, `branch_before`, `branch_after`, `commits`, `next_step`,
`reports_dir`, `build_tracking_path`, `handoff_path`, `todo_files`,
`fix_commits`. The orchestrator can derive these from git or from its own
state.

**Additions (pattern-recognition, architecture-strategist):** Added
`failure_reason` (existing agents embed reason in STATUS line -- manifest
needs parity). Added `manifest_version` (schema evolution detection).

**Flattening (agent-native-reviewer):** Feed-Forward uses flat keys instead
of nested YAML. The orchestrator parses manifests via Read + pattern
matching, not a YAML parser. Nested structures are fragile. All values
MUST be single-line strings.

Common fields (all bundles):
```yaml
manifest_version: 1
phase_name: "brainstorm"
phase_status: "IN_PROGRESS"
failure_reason: ""
recovery_point: "abc1234"
feed_forward_hardest_decision: "..."
feed_forward_rejected_alternatives: "..."
feed_forward_least_confident: "..."
```

Bundle-specific fields (present when applicable, not deterministic paths):
```yaml
brainstorm_path: "docs/brainstorms/<file>.md"
plan_path: "docs/plans/<file>.md"
review_summary_path: "docs/reports/<run-id>/review-summary.md"
solution_doc_path: "docs/solutions/<file>.md"
p1_count: 0
p2_count: 0
```

**This is the canonical manifest contract.** All bundle implementation
steps, acceptance tests, and verification commands in this plan reference
these fields only. Fields removed during deepening (timestamps, branch
names, commit lists, deterministic paths like reports_dir) are NOT part
of the contract -- the orchestrator derives them from git or its own state.

Manifest paths (deterministic, known before agent spawns):
- Bundle 1: `docs/reports/phase-brainstorm.manifest.yaml`
- Bundle 2: `docs/reports/phase-plan.manifest.yaml`
- Bundle 3: `docs/reports/<run-id>/phase-deepen.manifest.yaml`
- Bundle 4: `docs/reports/<run-id>/phase-review.manifest.yaml`
- Solo work: `docs/reports/<run-id>/phase-work.manifest.yaml`

Bundles 1-2 write to `docs/reports/` (no run-id yet). Bundles 3-4 and
solo work write under `docs/reports/<run-id>/`.

### Feed-Forward Consumer Chain

Each phase consumes Feed-Forward from its immediately prior phase's
manifest. The orchestrator extracts `feed_forward_*` fields from the
completed manifest and injects them into the next phase agent's prompt.

```
Bundle 1 (brainstorm) -- produces brainstorm Feed-Forward
  ↓ consumed by
Bundle 2 (plan) -- produces plan Feed-Forward
  ↓ consumed by
Bundle 3 (deepen) -- produces deepen Feed-Forward
  ↓ consumed by
  ├─ Solo path: phase-work agent -- produces work Feed-Forward
  │     ↓ consumed by
  │   Bundle 4 (review)
  └─ Swarm path: Steps 7w-16w inline (no manifest produced)
        ↓ deepen Feed-Forward passes through
      Bundle 4 (review)
```

Rule: a phase NEVER reaches back past its immediate predecessor. Bundle 3
reads plan manifest, not brainstorm manifest. Bundle 4 reads work manifest
(solo) or deepen manifest (swarm), never plan manifest.

### Research Insights: Stale Manifest Protection

**(architecture-strategist, orchestrating-swarms, pattern-recognition):**
Bundles 1-2 manifests at non-run-scoped paths can collide with stale
manifests from prior runs.

**REQUIRED:** The orchestrator MUST delete `docs/reports/phase-brainstorm.manifest.yaml`
and `docs/reports/phase-plan.manifest.yaml` at Step 2.5, BEFORE spawning
Bundle 1. Failure to do this causes stale-manifest collision on re-runs.
This is not optional cleanup -- it is a correctness precondition.

Manifest lifecycle (simplified per code-simplicity-reviewer):
1. Agent writes sentinel manifest at phase start: `phase_status: IN_PROGRESS`,
   `recovery_point: <current HEAD>`. Two fields only.
2. Agent writes full manifest at phase end with `phase_status: PASS` or
   `FAIL` + all artifact paths + feed_forward fields. This overwrites
   the sentinel.
3. `phase_status: PASS` MUST be the absolute last Write operation before
   the agent exits -- after all commits are verified. (architecture-strategist)
4. Orchestrator reads manifest only AFTER the Agent tool call returns
   (agent exited), never while running. (agent-native-architecture)
5. If `phase_status` is still `IN_PROGRESS`, the agent died. Treat as failure.

**1b. Create phase-brainstorm.md agent**

File: `.claude/agents/phase-brainstorm.md`

Frontmatter:
```yaml
---
name: phase-brainstorm
description: Non-interactive brainstorm + refinement phase for autopilot. Use when autopilot dispatches the brainstorm phase.
tools: Read, Write, Edit, Glob, Grep, Bash, Agent
model: sonnet
source_workflow: compound-engineering/2.35.2/brainstorm
---
```

### Non-Interactive Encoding Contract (ALL PHASE AGENTS)

Phase agents MUST NOT invoke `/workflows:*` or `/compound-engineering:*`
skills via the Skill tool. All workflow logic is re-implemented inline in
the agent body as numbered Rules. This is not a wrapper pattern -- it is a
full re-encoding with all interactive decision points pre-resolved.

This contract exists because: (a) spawned agents cannot reliably invoke
Skills, (b) existing workflows are interactive and would prompt, breaking
the zero-prompt guarantee, (c) the brainstorm's Key Decision 2 explicitly
rejected wrapping interactive workflows.

### Agent Body Structure (ALL PHASE AGENTS)

Follow the 5-section pattern (extending the existing agents with Injected Context):

```
## Role
[One paragraph: what this agent does, single responsibility]

## Inputs
[Numbered list of arguments the orchestrator provides]

## Injected Context (provided by orchestrator at spawn time)
- **Expanded Brief:** {{path or content}}
- **Prior Phase Feed-Forward:** {{from previous manifest}}
- **Applied Lessons:** {{from compound-start}}
- **Agent Pitfalls:** {{from Step 1.6}}
- **Run State:** solo|swarm, run-id={{run_id}}, branch={{branch}}

## Rules
[Numbered imperatives. ALL of these for every agent:]
1. Do not invoke /workflows:* or /compound-engineering:* skills.
2. If any step would normally ask a clarifying question, choose the
   simplest option. Do not wait for input.
3. Always include Feed-Forward section (three questions) in output doc.
4. Write manifest sentinel at phase start (IN_PROGRESS).
5. Write final manifest with PASS/FAIL as absolute last operation.
6. [Bash command rules: one command per call, no cd&&, no loops, etc.]
7. [Phase-specific rules...]

## Output Contract
[Exact manifest YAML template with all required fields and STATUS rules.
Include example of PASS and FAIL manifests.]
```

Agent body encodes the brainstorm workflow logic with these autopilot
defaults for all interactive decision points:
- If asked clarifying questions: pick the simplest option
- If asked to choose approach: pick the simplest, most focused interpretation
- If asked for user input: make the decision autonomously
- Always include Feed-Forward section (three questions)
- Run brainstorm-refinement agent after brainstorm doc is written
- Write manifest to `docs/reports/phase-brainstorm.manifest.yaml`
- Include feed_forward fields in manifest

**1c. Modify autopilot SKILL.md -- Bundle 1 delegation**

Replace Step 3 (inline `/workflows:brainstorm`) and Step 4 (inline
brainstorm-refinement agent) with:

```
### Step 2.5: Persist Brief + Clean Stale Manifests

1. Write the expanded brief to `docs/reports/expanded-brief.md` so all
   phase agents can read it from disk. (orchestrating-swarms finding)
2. Delete `docs/reports/phase-brainstorm.manifest.yaml` if it exists.
3. Delete `docs/reports/phase-plan.manifest.yaml` if it exists.
   (Prevents stale manifest collision from prior runs.)

### Step 3: Brainstorm (Delegated)

1. Read agent-pitfalls from Step 1.6.
2. Spawn the phase-brainstorm agent:
   - mode: "bypassPermissions"
   - run_in_background: false (sequential -- need result before plan)
   - Prompt includes: expanded brief path, applied lessons from Step 1,
     agent-pitfalls. (No prior manifest -- brainstorm is the first phase.)
3. After agent completes, read `docs/reports/phase-brainstorm.manifest.yaml`.
4. Verify:
   - phase_status is PASS
   - brainstorm_path exists on disk
   - feed_forward fields are present
5. If FAIL or IN_PROGRESS: retry once. If still fails, abort pipeline.
6. Extract feed_forward from manifest for injection into plan phase.
```

Remove Step 4 (brainstorm-refinement) since it's now internal to the
phase-brainstorm agent.

**1d. First-rollout side-by-side validation**

Run the same brief through:
- Current inline path (brainstorm + refinement)
- New delegated path (phase-brainstorm agent)

**Model isolation rule:** Both paths MUST run at `model: sonnet` during
validation. The inline path normally runs at session model (often Opus).
Lock it to Sonnet for the comparison so any quality difference is
attributable to delegation, not model capability. This applies to all
per-bundle side-by-side validations (1d, 2c, 3c, 4b, 5b).

Compare for semantic equivalence per acceptance criteria:
- Brainstorm doc exists in docs/brainstorms/ with Feed-Forward section
- Scope preserved from expanded brief
- Refinement result equivalent
- Manifest complete and parseable

**Deliverables:**
- `.claude/agents/phase-brainstorm.md`
- Modified `.claude/skills/autopilot/SKILL.md` (Steps 3-4 replaced)
- Side-by-side validation results documented

#### Phase 2: Bundle 2 (Plan + Document Review x2)

**Goal:** Second harness validation, produces plan manifest that Bundle 3
depends on. Must land before Bundle 3 because the deepen agent consumes
Feed-Forward from `phase-plan.manifest.yaml`.

**2a. Create phase-plan.md agent**

File: `.claude/agents/phase-plan.md`

Frontmatter:
```yaml
---
name: phase-plan
description: Non-interactive plan + document-review phase for autopilot. Use when autopilot dispatches the plan phase.
tools: Read, Write, Edit, Glob, Grep, Bash
model: sonnet
source_workflow: compound-engineering/2.35.2/plan,document-review
---
```

### What phase-plan.md preserves from /workflows:plan

The current `/workflows:plan` has conditional research steps. In the
delegated V1 agent:

- **Preserved:** Local repo research (Glob + Grep for patterns, Read for
  CLAUDE.md guidance, Read for docs/solutions/ learnings). Uses the
  agent's own Read/Glob/Grep tools -- no child agents needed.
- **Preserved:** Plan generation with frontmatter, Feed-Forward, EARS
  acceptance criteria, Plan Quality Gate (4 questions).
- **Preserved:** Two document-review passes (encoded inline).
- **Scoped down:** External research (web search, framework docs, best
  practices agents) is intentionally skipped in V1 autopilot. The
  brainstorm and deepen phases already incorporate external research.
  The plan agent focuses on structuring what's already known.
- **Scoped down:** No interactive research decision ("Should I research
  externally?"). The agent always runs local-only research.

This is why `Agent` is removed from phase-plan's tools -- it does not
spawn research subagents. All research is local file reads.

Agent body encodes:
1. Read brainstorm doc from disk (brainstorm_path from prior manifest)
2. Write manifest sentinel to `docs/reports/phase-plan.manifest.yaml`
3. Run local research (Glob for patterns, Read for CLAUDE.md + solutions)
4. Generate plan (non-interactive, all decisions auto-resolved):
   - Frontmatter with Feed-Forward and swarm flag
   - EARS acceptance criteria
   - Plan Quality Gate: 4 questions answered
5. Run document-review logic pass 1 (non-interactive, auto-accept,
   choose "refine again")
6. Run document-review logic pass 2 (non-interactive, auto-accept,
   choose "complete")
7. Commit plan
8. Update manifest: `phase_status: PASS`, plan_path, feed_forward fields

**2b. Modify autopilot SKILL.md -- Bundle 2 delegation**

Replace Step 5 with delegated spawn:

```
### Step 5: Plan (Delegated)

1. Spawn the phase-plan agent:
   - mode: "bypassPermissions"
   - run_in_background: false
   - Prompt includes: brainstorm_path (from brainstorm manifest),
     expanded brief path, agent-pitfalls,
     Feed-Forward from brainstorm manifest (phase-brainstorm.manifest.yaml).
2. After agent completes, read `docs/reports/phase-plan.manifest.yaml`.
3. Verify:
   - phase_status is PASS
   - plan_path exists on disk
   - feed_forward fields are present
4. If FAIL or IN_PROGRESS: retry once. Abort on second failure.
5. Extract plan_path and feed_forward for injection into deepen phase.
```

**2c. First-rollout side-by-side validation**

**Model isolation rule:** Both paths MUST run at `model: sonnet` during
validation (see Phase 1, Step 1d for rationale).

Compare delegated plan agent output against inline plan+doc-review:
- Plan doc exists in docs/plans/ with frontmatter + Feed-Forward
- Carries forward brainstorm decisions
- Implementation-ready quality (EARS, Quality Gate)
- Doc-review improvements applied
- Manifest complete and parseable

**Deliverables:**
- `.claude/agents/phase-plan.md`
- Modified `.claude/skills/autopilot/SKILL.md` (Step 5 replaced)
- Side-by-side validation results

---

#### Phase 3: Bundle 3 (Deepen + Merge + Audit)

**Goal:** Validate atomic delegation with child agents and self-merge audit.
This is the hardest migration because the deepen agent must:
- Spawn its own parallel research children
- Collect all outputs
- Self-merge into the canonical plan
- Persist full audit trail (raw outputs + merge ledger)
- Commit everything atomically

**3a. Create phase-deepen.md agent**

File: `.claude/agents/phase-deepen.md`

Frontmatter:
```yaml
---
name: phase-deepen
description: Non-interactive deepen + merge phase for autopilot. Use when autopilot dispatches the deepen phase.
tools: Read, Write, Edit, Glob, Grep, Bash, Agent
model: sonnet
source_workflow: compound-engineering/2.35.2/deepen-plan,document-review
---
```

### Research Insights: Deepen as Nested Orchestrator

**(orchestrating-swarms, HIGH):** The deepen agent spawns parallel research
children, making it a nested orchestrator. Risks: (a) context cascade --
it uses its own window to coordinate children, same exhaustion risk one
level deeper; (b) if the agent dies after some children complete, partial
outputs may conflict with retry.

**Recovery protocol:** If `docs/reports/<run-id>/deepen-raw/` exists and
contains outputs from a prior attempt, skip child spawning and proceed
directly to merge. This avoids re-doing completed research on retry.

**Conflict model:** Research children write to separate files in
`deepen-raw/` -- never to the plan file directly. Only the parent deepen
agent merges into the canonical plan (single-writer pattern).

**Grandchild permissions (agent-native-reviewer):** When the deepen agent
spawns research children via the Agent tool, it must pass
`mode: "bypassPermissions"` to each child. Add a test case in Bundle 3
validation verifying permission propagation through two levels.

Agent body encodes:
1. Read plan from disk (plan_path provided by orchestrator)
2. Write manifest sentinel to `docs/reports/<run-id>/phase-deepen.manifest.yaml`
3. Check if `docs/reports/<run-id>/deepen-raw/` exists with outputs from
   a prior attempt. If yes, skip steps 4-5 (recovery shortcut).
4. Discover available skills (same pattern as current deepen-plan)
5. Spawn parallel research agents per plan section. Each child writes
   output to `docs/reports/<run-id>/deepen-raw/{section-name}.md`.
   Children MUST use `mode: "bypassPermissions"`.
6. Reconcile conflicts (if multiple agents modify same section)
7. Write merged canonical plan (overwriting plan file)
8. Write `docs/reports/<run-id>/deepening-applied.md` (merge ledger:
   section, contributing agents, accepted changes, rejected changes,
   rationale)
9. Run document-review logic twice (non-interactive, auto-accept all
   changes, choose "refine again" after first pass, choose "complete"
   after second). Do NOT invoke `/compound-engineering:document-review`
   skill -- encode the logic inline per Non-Interactive Encoding Contract.
10. Commit plan + audit trail + raw outputs
11. Update manifest: `phase_status: PASS`, artifact paths, feed_forward
    fields. This MUST be the last Write operation.

Note: Steps 6.05 and 6.07 (document-review x2) are absorbed into this
bundle. The deepen agent runs doc-review internally after the merge,
keeping the polished plan in the same context as the deepening work.

**3b. Modify autopilot SKILL.md -- Bundle 3 delegation**

Replace Steps 6, 6.05, 6.07, and 6.5 with:

```
### Step 6: Deepen + Merge + Review (Delegated)

1. Spawn the phase-deepen agent:
   - mode: "bypassPermissions"
   - run_in_background: false
   - Prompt includes: plan_path, run-id, reports_dir, agent-pitfalls,
     Feed-Forward from plan manifest (phase-plan.manifest.yaml).
2. After agent completes, read manifest at
   docs/reports/<run-id>/phase-deepen.manifest.yaml.
3. Verify:
   - phase_status is PASS
   - plan_path file exists and was modified
   - deepening-applied.md exists in reports dir
   - deepen-raw/ directory exists with at least one file
   - feed_forward fields present
4. If FAIL or IN_PROGRESS: retry once. Abort on second failure.
5. Extract plan_path and feed_forward for next phase (work or swarm).
```

Remove Steps 6.05, 6.07, and 6.5 (all absorbed into phase-deepen agent).

**3b.1. Heuristic adjustment (inline with Bundle 3 delivery)**

After Bundle 3 is validated and merged, update the context-budget
checkpoint formula in SKILL.md to zero out the deepening contribution:

```
load = swarm_agents + (review_agents * 1.5) + (fix_retries * 3)
```

(Previously: `deepening_agents * 2` was included. Delegated deepen agents
no longer contribute to orchestrator context, so this term becomes 0.)

**3c. First-rollout side-by-side validation**

**Model isolation rule:** Both paths MUST run at `model: sonnet` during
validation (see Phase 1, Step 1d for rationale).

Compare delegated deepen agent output against inline deepen+merge+doc-review:
- Canonical plan produced (single source of truth)
- Deepening-applied.md exists with per-section ledger
- Raw outputs preserved in deepen-raw/
- Doc-review improvements applied
- Substantive deepening corrections match inline path

**Deliverables:**
- `.claude/agents/phase-deepen.md`
- Modified `.claude/skills/autopilot/SKILL.md` (Steps 6, 6.05, 6.07, 6.5 replaced)
- Side-by-side validation results

#### Phase 4: Bundle 4 (Review + Resolve TODOs + Compound)

**Goal:** Heaviest, most coupled migration. By this point the harness is proven.

**V1 scope: Bundle 4 is strictly monolithic.** The brainstorm's
least-confident item (whether compound can split from review+resolve) is
acknowledged but deferred to a follow-up plan. This plan builds one
`phase-review.md` agent that runs all three workflows. If the agent prompt
exceeds 300 lines static, use a companion reference file
(`.claude/agents/phase-review-reference.md`) per the prompt size cap.

**Follow-up work (NOT in this plan):** Run a compound disk-isolation
experiment in a separate session to determine whether compound can read
everything it needs from disk. Results inform a V2 unbundling plan.

**4a. Create phase-review.md agent**

File: `.claude/agents/phase-review.md`

Frontmatter:
```yaml
---
name: phase-review
description: Non-interactive review + resolve + compound phase for autopilot. Use when autopilot dispatches the review phase.
tools: Read, Write, Edit, Glob, Grep, Bash, Agent
model: sonnet
source_workflow: compound-engineering/2.35.2/review,resolve_todo_parallel,compound
---
```

Agent body encodes:
1. Read plan, built code, and reports dir. Consumes Feed-Forward from
   deepen manifest (or work manifest for solo path, provided by orchestrator).
2. Write manifest to `docs/reports/<run-id>/phase-review.manifest.yaml`
   with `phase_status: IN_PROGRESS`
3. Run review workflow logic (spawn multi-agent review, synthesize findings,
   create todo files). Review agents scrutinize Feed-Forward "least
   confident" item from plan.
4. Run resolve_todo_parallel logic (read todos, prioritize, fix, commit)
5. Run compound workflow logic (spawn subagents for context analysis,
   solution extraction, categorization; assemble solution doc with
   Risk Resolution section tracing Feed-Forward chain)
6. Commit all artifacts
7. Update manifest: `phase_status: PASS`, review_summary_path,
   solution_doc_path, p1_count, p2_count, feed_forward fields

V1 constraint: compound stays bundled with review+resolve. Do not split.
(see brainstorm: Key Decision, Bundle 4)

**4b. Modify autopilot SKILL.md -- Bundle 4 delegation**

Replace Review, Resolve TODOs, and Compound sections in Shared Tail with:

```
### Review + Resolve + Compound (Delegated)

1. Spawn the phase-review agent:
   - mode: "bypassPermissions"
   - run_in_background: false
   - Prompt includes: plan_path, run-id, reports_dir, agent-pitfalls,
     Feed-Forward from the immediately prior delegated phase:
       - Solo path: from work manifest (phase-work.manifest.yaml)
       - Swarm path: from deepen manifest (phase-deepen.manifest.yaml)
         (swarm steps 7w-16w are inline and don't produce a manifest)
2. After agent completes, read manifest at
   docs/reports/<run-id>/phase-review.manifest.yaml.
3. Verify:
   - phase_status is PASS
   - solution_doc_path exists on disk
   - review_summary_path exists on disk
   - feed_forward fields present
4. If FAIL or IN_PROGRESS: retry once. Abort on second failure.
5. Extract solution_doc_path and review data for tail steps.
```

**4b.1. Heuristic adjustment (inline with Bundle 4 delivery)**

After Bundle 4 is validated and merged, update the context-budget
checkpoint formula in SKILL.md to zero out the review contribution:

```
load = swarm_agents + (fix_retries * 3)
```

(Previously: `review_agents * 1.5` was included. Delegated review agent
no longer contributes to orchestrator context, so this term becomes 0.
Combined with the Bundle 3 adjustment, only swarm agents and fix retries
remain in the formula.)

**Deliverables:**
- `.claude/agents/phase-review.md`
- Modified `.claude/skills/autopilot/SKILL.md` (Shared Tail partially replaced)
- Side-by-side validation results

#### Phase 5: Solo Work Phase

**Goal:** Standalone, high token savings. Can parallel with Phase 4.

**5a. Create phase-work.md agent**

File: `.claude/agents/phase-work.md`

Frontmatter:
```yaml
---
name: phase-work
description: Non-interactive work phase for autopilot solo path. Use when autopilot dispatches the solo work phase.
tools: Read, Write, Edit, Glob, Grep, Bash
model: sonnet
source_workflow: compound-engineering/2.35.2/work
---
```

Agent body encodes:
1. Read plan from disk (plan_path from deepen manifest)
2. Write manifest to `docs/reports/<run-id>/phase-work.manifest.yaml`
   with `phase_status: IN_PROGRESS`
3. Run work workflow logic (non-interactive):
   - Environment setup
   - Todo creation from plan
   - Implementation loop with incremental commits (~50-100 lines each)
   - FC8 smoke test rules (write to file, not inline python)
   - Continuous testing
4. Update manifest: `phase_status: PASS`, feed_forward fields

**5b. Modify autopilot SKILL.md -- Solo work delegation**

Replace Step 7s with delegated spawn:

```
### Step 7s: Work (Delegated)

1. Spawn the phase-work agent:
   - mode: "bypassPermissions"
   - run_in_background: false
   - Prompt includes: plan_path (from deepen manifest), run-id,
     reports_dir, agent-pitfalls,
     Feed-Forward from deepen manifest (phase-deepen.manifest.yaml).
2. After agent completes, read manifest at
   docs/reports/<run-id>/phase-work.manifest.yaml.
3. Verify:
   - phase_status is PASS
   - feed_forward fields present
4. If FAIL or IN_PROGRESS: retry once. Abort on second failure.
5. Extract feed_forward for injection into review phase.
```

**Deliverables:**
- `.claude/agents/phase-work.md`
- Modified `.claude/skills/autopilot/SKILL.md` (Step 7s replaced)
- Side-by-side validation results

#### Phase 6: Dispatcher Cleanup + Context Budget Update

**Goal:** Clean up the autopilot SKILL.md after all bundles are migrated.

Tasks:
1. Remove all inline phase logic that's been replaced by agents
2. Verify context-budget heuristic is correct (should already be
   `load = swarm_agents + (fix_retries * 3)` from Phase 3 and Phase 4
   incremental adjustments -- confirm no stale terms remain)
3. Update the CHECKPOINT.md schema to include manifest paths
4. Verify tail-resume can read phase manifests from deterministic paths
5. Update the flow diagram comments in SKILL.md
6. Remove steps that no longer exist (old step numbers)
7. Renumber remaining steps for clarity

## Alternative Approaches Considered

See brainstorm: docs/brainstorms/2026-05-23-autopilot-agent-delegation-brainstorm.md,
"Rejected alternatives" in Feed-Forward section.

1. Session chaining via remote triggers -- band-aid, only rescues tail
2. Shell script pipeline -- loses adaptive orchestration
3. Individual phase delegation -- Codex identified coupling, forces bundles
4. Wrapping interactive workflows -- P1 blocker, breaks zero-prompt
5. Returned manifests -- conflicts with explicit-disk-state principle

## System-Wide Impact

### Interaction Graph

Autopilot SKILL.md dispatches phase agents -> each agent reads/writes disk
artifacts -> orchestrator reads manifests -> orchestrator runs tail steps.
No callbacks or middleware. File-based communication only.

### Error & Failure Propagation

- Phase agent FAIL or context death: orchestrator reads manifest. Then:
  1. Check git log for commits after `recovery_point`. If any exist,
     run `git reset --hard <recovery_point>` to discard partial commits
     and restore the repo to the last known good state. (This is a
     destructive operation but is safe because all commits after
     recovery_point are from a failed phase that will be retried.)
  2. Re-spawn the phase agent with the same prompt. Max 1 retry, abort
     on second failure.
  3. What survives a retry: disk artifacts that are NOT in git (manifest
     sentinel, deepen-raw/ outputs from completed children). What is
     discarded: partial commits from the failed attempt.
  This follows the "disk is working memory" principle: committed state
  resets, but disk artifacts outside git persist for recovery shortcuts.
- Deepen agent death with partial children: if `deepen-raw/` exists with
  outputs from completed children, the retry skips child spawning and
  proceeds directly to merge (recovery shortcut). The deepen-raw/ files
  survive the `git reset --hard` because they are untracked or were
  written before any commit. (orchestrating-swarms)
- Orchestrator context death: CHECKPOINT.md captures last completed phase +
  all manifest paths. /tail-resume reads manifests directly.
- Pipeline abort: write `docs/reports/pipeline-abort.manifest.yaml` with
  `pipeline_status: ABORTED`, failing phase, and error. Do NOT clean up
  partial artifacts -- they are diagnostic. (architecture-strategist)

### State Lifecycle Risks

- Partial manifest write: agent dies between creating manifest and updating
  final status. Mitigation: IN_PROGRESS is the default state, treated as
  failure by orchestrator.
- Orphaned deepen-raw files: if pipeline aborts after Bundle 3, raw outputs
  persist in docs/reports/<run-id>/deepen-raw/. Acceptable -- they're
  audit artifacts, not temp files.

### API Surface Parity

No external APIs affected. This is internal tooling. The autopilot SKILL.md
is the only consumer of phase agents. /tail-resume is updated to read
manifest paths.

### Integration Test Scenarios

1. **Happy path solo:** Orchestrator spawns all 5 bundles sequentially,
   each writes PASS manifest, tail completes in same session.
2. **Phase agent failure + retry:** Bundle 1 agent writes FAIL manifest,
   orchestrator retries once, second attempt succeeds.
3. **Phase agent context death:** Bundle 3 agent dies mid-merge, manifest
   shows IN_PROGRESS, orchestrator retries from recovery_point.
4. **Swarm path with delegated phases:** Bundles 1-3 delegated, Steps 7w-16w
   inline, Bundle 4 delegated, tail completes.
5. **Feed-Forward chain preservation:** Each bundle's manifest includes
   feed_forward fields, orchestrator injects into next bundle's prompt,
   review agent addresses "least confident" item.

## Acceptance Criteria

### Functional Requirements

- [ ] All 5 phase agents created in .claude/agents/phase-*.md
- [ ] Autopilot SKILL.md rewritten as dispatcher
- [ ] Each phase agent writes manifest to deterministic path
- [ ] Manifest lifecycle works (IN_PROGRESS -> PASS/FAIL)
- [ ] Feed-Forward chain preserved across delegated phases
- [ ] Deepen agent produces canonical plan + full audit trail
- [ ] Review agent runs review + resolve + compound atomically
- [ ] Swarm path (Steps 7w-16w) unchanged and functional
- [ ] Tail steps (learnings, BUILD_TRACKING, self-audit) have room to complete

### Non-Functional Requirements

- [ ] Orchestrator peak context stays below 30k tokens for 15-agent swarm
- [ ] No regression in artifact quality (solution docs, BUILD_TRACKING)
- [ ] Each phase agent follows Bash command rules (one command per call)
- [ ] All agents spawned with mode: "bypassPermissions"

### Context Budget Verification

How to observe context-budget success during rollout: the autopilot
pipeline completes the shared tail (Update Learnings through Self-Audit)
without triggering the context-budget checkpoint gate and without
requiring /tail-resume. If the pipeline writes `<promise>DONE</promise>`
in the same session that started the build, the context budget is proven
sufficient. If the checkpoint fires or the session dies before DONE,
the budget exceeded the target.

### Quality Gates

- [ ] Side-by-side validation passes for each bundle on first rollout
- [ ] Existing swarm build passes end-to-end with delegated phases
- [ ] Solo build passes end-to-end with delegated phases
- [ ] /tail-resume still works (reads manifest paths if available)

## Acceptance Tests (EARS)

### Happy Path

- WHEN autopilot runs a solo build with all phases delegated THE SYSTEM
  SHALL complete the full pipeline including shared tail without hitting
  context limits
- WHEN a phase agent completes successfully THE SYSTEM SHALL find a
  manifest file at the deterministic path with phase_status: PASS
- WHEN the orchestrator reads a PASS manifest THE SYSTEM SHALL extract
  feed_forward fields and inject them into the next phase agent's prompt
- WHEN the deepen agent completes THE SYSTEM SHALL have overwritten the
  plan file, created deepening-applied.md, and persisted raw outputs
  in deepen-raw/

### Error Cases

- WHEN a phase agent writes phase_status: FAIL THE SYSTEM SHALL retry
  the phase once from recovery_point and abort on second failure
- WHEN a phase agent dies without updating the manifest THE SYSTEM SHALL
  detect IN_PROGRESS status and retry from recovery_point
- WHEN a phase agent's manifest is missing required fields THE SYSTEM
  SHALL treat it as FAIL and retry
- WHEN a swarm build runs with Bundles 1-3 delegated and Steps 7w-16w
  inline THE SYSTEM SHALL maintain file-system and git isolation between
  delegated phase agents and inline swarm workers (no concurrent writes
  to same manifest or branch)

### Verification Commands

- `cat docs/reports/phase-brainstorm.manifest.yaml | grep phase_status`
  -- returns "PASS"
- `cat docs/reports/<run-id>/phase-deepen.manifest.yaml | grep plan_path`
  -- returns valid path
- `ls docs/reports/<run-id>/deepen-raw/` -- contains at least one file
- `cat docs/reports/<run-id>/phase-review.manifest.yaml | grep solution_doc_path`
  -- returns valid path in docs/solutions/

## What Must NOT Change

- Swarm path coordination (Steps 7w-16w) -- stays inline, hard V1 non-goal
- Mandatory tail artifacts (BUILD_TRACKING, solution doc, self-audit, HANDOFF)
- Agent-pitfalls injection into every agent brief
- All existing quality gates (spec consistency, completeness, ownership,
  contract check, smoke test)
- /tail-resume checkpoint recovery mechanism
- The file-based communication pattern (agents write STATUS reports)
- Maximum agent hierarchy depth: orchestrator -> phase agent -> child agent.
  No deeper nesting permitted. (architecture-strategist P3)

## Dependencies & Prerequisites

- No external dependencies. All changes are to local .claude/ files.
- Requires understanding of existing workflow skill logic to encode
  non-interactive equivalents in phase agents.
- Current compound-engineering plugin version: 2.35.2. Phase agents
  record this version in frontmatter `source_workflow` field.

### Pre-Implementation Preparation (MANDATORY)

Before starting Phase 1, read each marketplace skill source file and
create a summary of: (a) interactive decision points that need autopilot
defaults, (b) external tool/agent invocations, (c) side effects (file
writes, git operations). Skills to summarize:

1. `/workflows:brainstorm` -- `~/.claude/plugins/cache/every-marketplace/compound-engineering/2.35.2/commands/workflows/brainstorm.md`
2. `/workflows:plan` -- `commands/workflows/plan.md`
3. `/workflows:work` -- `commands/workflows/work.md`
4. `/workflows:review` -- `commands/workflows/review.md`
5. `/workflows:compound` -- `commands/workflows/compound.md`
6. `/compound-engineering:document-review` -- `skills/document-review/SKILL.md`
7. `/compound-engineering:deepen-plan` -- `commands/deepen-plan.md`

This scopes the actual re-encoding effort per agent. (agent-native-reviewer:
"the plan's biggest underestimate")

## Risk Analysis & Mitigation

### Maintenance drift (ACCEPTED V1 TRADEOFF)

Phase agents duplicate /workflows:* logic. When plugin updates, agents
can silently drift.

Mitigation: Each agent records source workflow version. Manual diff on
plugin update. Long-term: pre-flight version check.

### Prompt size degradation

Phase agent prompts may reach 500+ lines. Instruction-following could degrade.
Bundle 4 is the highest risk (3 workflows encoded), not Bundle 1.

Mitigation (agent-native-architecture, create-agent-skills):
- Test empirically on Bundle 2 or 3 (largest prompts), not Bundle 1.
- Hard cap: static agent prompts must not exceed 300 lines. If exceeded,
  move verbose templates to a companion reference file
  (`.claude/agents/phase-*-reference.md`) that the agent reads at start.
- Structure prompts in layers: Identity+Behavior (~30 lines), Outcome
  (~20 lines), Rules (~30 lines), Output Contract (~20 lines), Injected
  Context (variable). Keep static under 150 lines where possible.
- If degradation: split into invariant globals + bundle-specific rules +
  current artifact inputs.

### Self-justifying merges (Bundle 3)

Deepen agent merges its own research without external validation.

Mitigation: Full raw child outputs persisted alongside merge ledger.
Review agent can audit merge decisions in Bundle 4.

### Bundle 4 coupling assumption

Compound is assumed to need fresh review context. If wrong, Bundle 4
is over-bundled (one giant agent doing three jobs). V1 builds it
monolithic regardless. The prompt size cap (300 lines static + companion
reference file) keeps it manageable.

Mitigation: After V1 is complete, run a compound disk-isolation
experiment in a separate follow-up plan. If compound reads everything
from disk, V2 splits the bundle.

### Context budget heuristic becomes invalid during rollout

The current checkpoint heuristic
(`load = swarm_agents + (deepening_agents * 2) + (review_agents * 1.5) + (fix_retries * 3)`)
was calibrated against inline phases. As bundles are delegated, their
contributions to orchestrator context drop to near-zero.

Mitigation (architecture-strategist): Heuristic is updated incrementally
at the point of each bundle's delivery (not deferred to Phase 6):
- Phase 3 (Bundle 3): zero out `deepening_agents * 2` (Step 3b.1)
- Phase 4 (Bundle 4): zero out `review_agents * 1.5` (Step 4b.1)
- Phase 6: verify final formula `load = swarm_agents + (fix_retries * 3)`

### Tail step growth

The tail steps (learnings, BUILD_TRACKING, self-audit) are estimated at
~10k tokens. If they grow in future versions, the same context exhaustion
problem resurfaces -- now in the tail instead of phases.

Mitigation: Acknowledge as future risk. If tail exceeds ~15k tokens,
evaluate delegating tail steps as well. (architecture-strategist P3)

## Most Likely Way This Plan Is Wrong

The phase agents may need more context than expected to match inline
quality. When running inline, the orchestrator carries forward subtle
context (user intent nuances, edge cases discussed in brainstorm,
correction patterns from earlier phases) that doesn't make it into the
manifest or disk artifacts. Phase agents read docs from disk but may miss
this implicit context, producing technically correct but less informed
outputs. Bundle 1 validation will be the early signal -- if the brainstorm
agent produces a noticeably different doc from inline, the prompt design
needs enrichment beyond what's in the brief and pitfalls.

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-05-23-autopilot-agent-delegation-brainstorm.md](docs/brainstorms/2026-05-23-autopilot-agent-delegation-brainstorm.md)
  Key decisions carried forward: 5 bundles (not 8 phases), purpose-built
  non-interactive agents, deterministic on-disk manifests, Feed-Forward as
  typed manifest field, deepen owns merge atomically.

- **Pre-brainstorm brief:** [docs/briefs/2026-05-23-autopilot-agent-delegation-brief.md](docs/briefs/2026-05-23-autopilot-agent-delegation-brief.md)
  Two rounds of Codex review incorporated.

### Internal References

- Autopilot SKILL.md: `.claude/skills/autopilot/SKILL.md`
- Existing agent definitions: `.claude/agents/*.md` (10 agents, all follow
  same frontmatter format)
- Context optimization solution: `docs/solutions/2026-05-20-autopilot-context-window-optimization.md`
  ("Disk is the working memory of the orchestrator")
- Swarm orchestration solution: `docs/solutions/2026-04-09-autopilot-swarm-orchestration.md`
  (file-based contracts, STATUS signals)
- Autonomy hardening solution: `docs/solutions/2026-05-13-sandbox-autonomy-hardening.md`
  ("enforcement in skill, not prose")
- Tail resume skill: `.claude/skills/tail-resume/SKILL.md`
- Workflow skills: `~/.claude/plugins/cache/every-marketplace/compound-engineering/2.35.2/commands/workflows/`

## Feed-Forward

- **Hardest decision:** How much workflow logic to encode in each phase
  agent vs. how much to leave implicit. Too little and the agent misses
  steps. Too much and the prompt degrades. Bundle 2 or 3 (largest prompts)
  is the calibration point.

- **Rejected alternatives:** Wrapping interactive workflows (P1 blocker),
  returned manifests (conflicts with disk-state principle), individual
  phase delegation (coupling forces bundles), shell script pipeline
  (loses adaptive orchestration).

- **Least confident:** Whether compound can eventually be split from
  review+resolve in Bundle 4. The V1 assumption is that compound needs
  fresh review context, but this hasn't been tested. During Bundle 4
  rollout, observe what compound actually reads from context vs. disk.
  If everything comes from disk, V2 can split the bundle.
