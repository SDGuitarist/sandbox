Read HANDOFF.md and CLAUDE.md for project context.
Read .claude/skills/autopilot/SKILL.md for the current autopilot pipeline.
Read docs/solutions/2026-05-20-autopilot-context-window-optimization.md for prior work on this problem.

# Autopilot Agent Delegation: Pre-Brainstorm Brief

## Problem Statement

The autopilot pipeline consistently runs out of context window before
completing its mandatory tail steps (learnings propagation, BUILD_TRACKING
fill, self-audit, verify self-audit). This was partially addressed in
Run 050 by adding a context-budget checkpoint gate (load > 30 pauses and
writes CHECKPOINT.md), but the checkpoint is a band-aid -- it only rescues
the tail by requiring a manual /tail-resume in a new session. The root cause
remains: the orchestrator accumulates the full output of every phase
(brainstorm, plan, deepen, document-review x2, work, review, compound) in
its own context window.

## Current Architecture

The autopilot orchestrator runs every phase inline in a single session:

```
Orchestrator context accumulates:
  Step 1:   /compound-start          ~2k tokens (lessons, session context)
  Step 2:   Expand Brief             ~1k tokens
  Step 3:   /workflows:brainstorm    ~5-8k tokens (full brainstorm dialogue)
  Step 4:   brainstorm-refinement    ~1-2k tokens (agent output)
  Step 5:   /workflows:plan          ~8-12k tokens (full plan generation)
  Step 6:   /deepen-plan             ~10-15k tokens (4+ parallel research agents)
  Step 6.05: /document-review        ~3-5k tokens (first refine pass)
  Step 6.07: /document-review        ~3-5k tokens (second refine pass)
  Step 6.5: Merge deepening          ~2-3k tokens
  [SOLO]
  Step 7s:  /workflows:work          ~20-40k tokens (implementation + commits)
  [SWARM]
  Step 10w: Parallel agents          ~5-15k tokens (agent outputs returned)
  Step 11w: Assembly merge           ~3-5k tokens
  Steps 12-14w: Verification        ~5-10k tokens (contract, smoke, test)
  [SHARED TAIL]
  Review:   /workflows:review        ~15-25k tokens (multi-agent review)
  Resolve TODOs:                     ~5-10k tokens
  Compound: /workflows:compound      ~5-8k tokens
  Update Learnings:                  ~3-5k tokens
  BUILD_TRACKING fill:               ~2-3k tokens
  Self-audit + verify:               ~5-8k tokens

  TOTAL ESTIMATE: 80-150k+ tokens accumulated in orchestrator context
```

Phases write their artifacts to disk (docs/brainstorms/, docs/plans/, git
commits, docs/reports/), but the orchestrator still holds all the intermediate
dialogue, tool call results, and coordination output in its context window.

## Proposed Solution: Phase-Level Agent Delegation (Option 2)

Refactor the autopilot so each major phase runs in its own spawned agent
with its own context window. The orchestrator becomes a thin dispatcher
that holds only short summaries and coordination logic.

### Proposed new orchestrator flow:

```
Orchestrator dispatches (bundle-aware):

  Setup (inline, ~5k total):
    Step 1:   /compound-start
    Step 1.5: BUILD_TRACKING
    Step 1.6: Read pitfalls
    Step 2:   Expand Brief

  Bundle 1 -- SPAWN brainstorm+refinement agent
    --> writes manifest to docs/reports/phase-brainstorm.manifest.yaml

  Bundle 2 -- SPAWN plan+doc-review agent
    --> writes manifest to docs/reports/phase-plan.manifest.yaml

  Coordination (inline, ~1k):
    Step 6.1: Generate run-id + create docs/reports/<run-id>/

  Bundle 3 -- SPAWN deepen+merge agent (receives run-id, writes to reports dir)
    --> writes manifest to docs/reports/<run-id>/phase-deepen.manifest.yaml

  Coordination (inline, ~0.5k):
    Branch point: read plan frontmatter

  [SOLO]
    SPAWN work agent
    --> writes manifest to docs/reports/<run-id>/phase-work.manifest.yaml

  [SWARM]
    Steps 7w-16w: stays top-level (hard non-goal for V1)

  Bundle 4 -- SPAWN review+resolve+compound agent
    --> writes manifest to docs/reports/<run-id>/phase-review.manifest.yaml

  Tail (inline, ~10k):
    Update Learnings
    BUILD_TRACKING fill
    Self-audit + verify

  ESTIMATED ORCHESTRATOR CONTEXT: 15-20k tokens (vs 80-150k+ currently)
```

### Why this works:

1. **Agents get their own full context window.** A brainstorm agent has the
   entire window for brainstorm work. A work agent has the entire window for
   implementation. No phase is constrained by what came before it.

2. **The orchestrator keeps adaptive intelligence.** Unlike Option 3 (shell
   script), the orchestrator still makes judgment calls -- reading agent
   outputs, deciding how to handle failures, adapting the flow.

3. **Disk is the working memory.** Phases pass state through files on disk
   (docs/brainstorms/, docs/plans/, git commits, docs/reports/), not through
   context. However, this is NOT true at all boundaries -- see Phase Bundles
   below for the coupled pairs that must be delegated together.

### Key challenge: Non-interactive phase agents

The existing workflow skills (/workflows:brainstorm, /workflows:plan,
/workflows:work, /document-review) are explicitly interactive -- they ask
user questions, request approval for edits, and offer handoff choices.
The current autopilot wraps some of this with "make decisions yourself"
logic (Step 3: "pick the simplest option and continue"), but a delegated
agent can't invoke skills via the Skill tool.

This means we need **purpose-built non-interactive phase agents** (as
.claude/agents/phase-*.md files), not thin wrappers around existing
workflows. Each phase agent encodes the workflow logic directly in its
prompt, with all interactive decision points pre-resolved to autopilot
defaults. The deepen-plan command already demonstrates this pattern --
it has subagents read SKILL.md files directly rather than invoking skills.

This is the core work of the project: authoring these phase agents.

### What stays in the orchestrator:

- Steps 1-2 (compound-start, BUILD_TRACKING, pitfalls, brief expansion) --
  lightweight setup, ~5k total
- Step 6.1 (run-id generation) -- trivial, ~0.5k
- Branch point decision -- reads plan frontmatter, trivial
- Swarm path coordination (Steps 7w-16w) -- stays top-level (hard non-goal
  for V1, see Non-Goals below)
- Shared tail: learnings, BUILD_TRACKING fill, self-audit -- ~10k, now has
  plenty of room

### What moves to agents (by bundle):

| Bundle | Phases included | Current tokens | On-disk manifest path |
|--------|----------------|---------------|----------------------|
| 1: Brainstorm | brainstorm + refinement | 6-10k | docs/reports/phase-brainstorm.manifest.yaml |
| 2: Plan | plan + doc-review x2 | 14-22k | docs/reports/phase-plan.manifest.yaml |
| 3: Deepen | deepen + merge + audit | 12-18k | docs/reports/\<run-id\>/phase-deepen.manifest.yaml |
| 4: Review | review + resolve + compound | 25-43k | docs/reports/\<run-id\>/phase-review.manifest.yaml |
| Solo work | work | 20-40k | docs/reports/\<run-id\>/phase-work.manifest.yaml |

**Total context saved: ~75-130k tokens**

## Non-Goals for V1

- **No delegated swarm coordination.** Steps 7w-16w stay top-level in the
  orchestrator. The default non-tmux backend is in-process -- teammates share
  the leader process and all die if the leader dies. Wrapping swarm coordination
  in a phase agent creates a bad failure shape. This is a hard non-goal.
- **No direct dependency on child Skill-tool invocation.** Phase agents will
  NOT call `/workflows:*` skills. They encode the workflow logic directly in
  their prompts with all interactive decisions pre-resolved.
- **No wrapping unchanged interactive workflows.** We are not wrapping existing
  skills in agents. We are authoring new non-interactive phase agents that
  implement the same logic without user prompts.

## Phase Artifact Contract

Every delegated phase agent writes a YAML manifest to a deterministic path
on disk. The orchestrator reads the manifest after the agent completes --
it does NOT depend on the agent's return value for state. This follows the
tail-resume design principle: explicit disk state, no "most recent" discovery.

### Manifest paths (deterministic, known before agent spawns):

- Bundle 1: `docs/reports/phase-brainstorm.manifest.yaml`
- Bundle 2: `docs/reports/phase-plan.manifest.yaml`
- Bundle 3: `docs/reports/<run-id>/phase-deepen.manifest.yaml`
- Solo work: `docs/reports/<run-id>/phase-work.manifest.yaml`
- Bundle 4: `docs/reports/<run-id>/phase-review.manifest.yaml`

Bundles 1 and 2 write to `docs/reports/` (no run-id yet). Bundles 3, 4,
and solo work write under `docs/reports/<run-id>/` (run-id exists by then).

### Manifest lifecycle:

1. Phase agent creates the manifest file at phase start with
   `phase_status: IN_PROGRESS` and `recovery_point: <current HEAD>`.
2. Phase agent updates fields incrementally as work progresses (e.g.,
   adding commit hashes after each commit).
3. Phase agent writes `phase_status: PASS` or `phase_status: FAIL` as
   the final update before exiting.
4. Orchestrator reads the manifest file. If `phase_status` is missing or
   still `IN_PROGRESS`, the agent died mid-execution -- treat as failure.

### Manifest schema (typed fields):

```yaml
# Common fields (all bundles)
phase_name: "brainstorm" | "plan" | "deepen" | "work" | "review"
phase_status: "IN_PROGRESS" | "PASS" | "FAIL"
started_at: "<ISO timestamp>"
completed_at: "<ISO timestamp or empty>"
branch_before: "<branch at phase start>"
branch_after: "<branch at phase end>"
recovery_point: "<last known good commit hash>"
commits:
  - "<hash>"
next_step: "<what the orchestrator should do next>"

# Bundle-specific typed fields (present when applicable)
brainstorm_path: "docs/brainstorms/<file>.md"
plan_path: "docs/plans/<file>.md"
reports_dir: "docs/reports/<run-id>/"
review_summary_path: "docs/reports/<run-id>/review-summary.md"
solution_doc_path: "docs/solutions/<file>.md"
build_tracking_path: "BUILD_TRACKING.md"
handoff_path: "HANDOFF.md"

# Review-specific fields (Bundle 4 only)
p1_count: 0
p2_count: 0
fix_commits:
  - "<hash>"
todo_files:
  - "<path>"
```

Not every bundle populates every field. The schema is a superset --
each bundle writes the fields it owns and leaves others absent.
The orchestrator and tail-resume read only the fields they need.

### Emergency salvage (context death with no manifest update):

If a phase agent dies without writing `phase_status: PASS` or `FAIL`,
the orchestrator:
1. Reads the manifest (will show `IN_PROGRESS` or be partially written).
2. Reads `recovery_point` to find the last good commit.
3. Checks git log for commits after `recovery_point` to assess partial work.
4. Default action: retry the full phase from `recovery_point`.

This is emergency salvage only, not the primary contract. The primary
contract is the deterministic manifest file at a known path.

## Phase Bundles

Phases are NOT independently delegatable. Some share in-memory state that
cannot be reconstructed from disk alone. Delegation must happen at the
bundle level:

### Bundle 1: Brainstorm + Refinement
- brainstorm writes doc -> refinement reads it from disk
- These ARE independently delegatable (disk-isolated)
- But bundling them is simpler: one agent does brainstorm + self-refinement

### Bundle 2: Plan + Document Review x2
- plan writes doc -> document-review reads it from disk
- These ARE independently delegatable
- But bundling keeps plan polish in one agent's context

### Bundle 3: Deepen + Merge (MUST be atomic)
- Step 6.5 depends on the orchestrator having deepening agent outputs in
  memory. If deepen runs in a delegated agent, those outputs won't be in
  the orchestrator's context.
- **Solution:** The deepen phase agent owns the merge. It spawns its research
  children, reconciles conflicts, writes the canonical plan, writes
  deepening-applied.md, commits both, and returns artifact paths.
- **New risk:** Self-justifying merges (agent merges its own edits without
  external validation). Mitigation: the phase agent persists raw child
  outputs AND a structured per-section merge ledger in docs/reports/<run-id>/
  so the orchestrator or review can audit the merge decisions.

### Bundle 4: Review + Resolve TODOs + Compound (MUST be bundled, V1 non-negotiable)
- review produces todo files -> resolve reads them -> compound wants fresh
  solved-problem context from the review+resolve cycle
- compound's workflow is built around assembling subagent text while context
  is fresh -- it is NOT yet proven disk-isolated enough to split from
  review/resolve
- **Solution:** One agent runs all three: review, resolve, compound. It has
  the full review context when writing the solution doc.
- **V1 constraint:** Do not attempt to split compound from review+resolve.
  If future evidence shows compound can read everything it needs from disk,
  this can be revisited in V2.

### Rollout order:
1. Bundle 1 first (brainstorm+refinement) -- simplest bundle, validates
   the phase-agent harness end-to-end: spawn agent -> agent writes
   deterministic on-disk manifest -> orchestrator reads manifest ->
   orchestrator advances. Proves the pattern works before tackling
   coupled phases.
2. Bundle 3 (deepen+merge) -- first coupled/hard migration. Validates
   atomic delegation with child agents and self-merge audit trail.
3. Bundle 2 (plan+doc-review) -- medium complexity, similar harness to
   Bundle 1 but with two doc-review passes.
4. Bundle 4 (review+resolve+compound) -- heaviest, most coupled. By this
   point the harness is proven and the hard patterns are established.
5. Solo work phase -- standalone, high token savings. Can be done in
   parallel with Bundle 4 since it has no coupling dependencies.

## Deepen Ownership

Step 6 (deepen-plan) and Step 6.5 (merge deepening into plan) become a
single delegated atomic phase. The orchestrator generates run-id and creates
docs/reports/<run-id>/ BEFORE spawning this agent, so the agent receives
the run-id and reports directory as inputs.

The deepen phase agent:

1. Writes initial manifest to `docs/reports/<run-id>/phase-deepen.manifest.yaml`
   with `phase_status: IN_PROGRESS`
2. Reads the plan document from disk
3. Spawns parallel research agents (its own children)
4. Collects all research outputs
5. Reconciles conflicts across sections (if multiple agents modified the same section)
6. Writes the merged canonical plan (overwriting the plan file)
7. Writes `docs/reports/<run-id>/deepening-applied.md` (audit trail)
8. Persists raw child outputs to `docs/reports/<run-id>/deepen-raw/` (merge audit)
9. Commits the plan, audit trail, and raw outputs
10. Updates manifest with `phase_status: PASS`, commit hashes, and artifact paths

The orchestrator never sees the raw research outputs. It reads the manifest
to get the merged plan path and can verify the merge via the audit trail.

## Failure and Resume Model

Every delegated phase must be resumable from disk alone, following the prior
solution's rule: "disk is the working memory of the orchestrator, not the
context window." The on-disk manifest at a deterministic path is the
primary contract -- the orchestrator never depends on agent return values
for state.

- **On phase-agent success:** Orchestrator reads the manifest file at the
  known path. Verifies `phase_status: PASS` and that listed artifact files
  exist on disk. Proceeds to next phase.
- **On phase-agent failure:** Orchestrator reads the manifest file. If
  `phase_status: FAIL`, reads `recovery_point` to find last good commit.
  Default: retry the full phase once from `recovery_point`, abort on
  second failure.
- **On phase-agent context death:** Manifest file will show
  `phase_status: IN_PROGRESS` (agent died before writing final status).
  Orchestrator reads `recovery_point` and checks git log for commits after
  that point to assess partial work. Default: retry the full phase from
  `recovery_point`. Git-log reconstruction is emergency salvage only.
- **Pipeline-level resume:** If the orchestrator itself dies, CHECKPOINT.md
  (already implemented) captures the last completed phase and all artifact
  paths. /tail-resume picks up from there. The deterministic manifest paths
  mean tail-resume can also read phase manifests directly without
  discovery heuristics.

## Risk: Maintenance Drift

Purpose-built non-interactive phase agents duplicate logic from the
/workflows:* skills and autopilot SKILL.md rules. When those upstream
sources change (new workflow steps, updated conventions, new agent-pitfalls
rules), the phase agents can silently fall behind.

**Source-of-truth ownership:**
- /workflows:* skills are the canonical interactive workflows (owned by
  the compound-engineering plugin, updated externally)
- .claude/agents/phase-*.md are the canonical autopilot phase agents
  (owned by this repo)
- autopilot SKILL.md is the orchestrator (owned by this repo)

**Mitigation:**
- Each phase agent's prompt header includes a `# Source Workflows` comment
  listing which /workflows:* skill(s) it was derived from and the version
  at time of authoring (e.g., `compound-engineering/2.35.2`)
- When the compound-engineering plugin updates, a manual diff between the
  new workflow version and the phase agent identifies drift
- Long-term: consider a pre-flight check that compares plugin version
  against the version recorded in phase agents and warns if mismatched

This is an accepted V1 tradeoff. The alternative (wrapping interactive
workflows) was rejected as a P1 blocker.

## Launch Constraints

All phase agents must be spawned with:
- `mode: "bypassPermissions"` -- zero-prompt guarantee
- Repo-root cwd -- project-local skills and settings only load from there
- Full project context injected: CLAUDE.md rules, agent-pitfalls, current
  plan path, and any prior phase manifests they need as input

## Alternatives Considered and Rejected

### Option 1: Session Chaining via Remote Triggers
After context exhaustion, fire a remote trigger that launches a new session
running /tail-resume. Problem: only rescues the tail, doesn't solve context
exhaustion during work or review phases. Band-aid, not a fix.

### Option 3: Multi-Session Pipeline with Shell Script
Split pipeline into 2-3 segments, run each as a separate `claude` CLI call.
Problem: loses adaptive orchestration. Each segment starts cold with no
shared context. Can't adjust the flow based on what happened in previous
segments. Most reliable but least intelligent.

### Option 4: Aggressive Context Pruning
Keep single-session architecture but discard content after each phase.
Problem: we don't control the compression behavior directly. The
orchestrator still generates all content even if it's later compressed.
Diminishing returns. Could complement Option 2 later but isn't a
standalone solution.

## Open Questions (Post-Codex Review)

Questions 1, 2, 4, 6, and 8 from the original brief were resolved by Codex
review. Remaining open questions:

1. **Feed-Forward chain:** The Feed-Forward framework requires each phase
   to address the previous phase's "least confident" item. Does this still
   work when phases run in isolated agents? The agent reads the previous
   phase's doc from disk, which contains the Feed-Forward section, so
   presumably yes -- but worth verifying during brainstorm.

2. **Testing strategy:** How do we validate that agent-delegated phases
   produce equivalent artifacts to inline phases? Run both side-by-side on
   the same input and diff the outputs? Or define acceptance criteria per
   phase agent (e.g., "brainstorm agent produces a valid brainstorm doc
   with Feed-Forward section")?

3. **Phase agent prompt size:** Purpose-built phase agents need the full
   workflow logic in their prompt. The largest workflows (work, review) are
   substantial. Are there practical prompt size limits for spawned agents
   that we need to design around?

4. **Deepen merge audit:** The deepen phase agent will self-merge its own
   research into the plan. What's the minimum audit trail that makes
   self-justifying merges detectable? Is a per-section merge ledger
   sufficient, or do we need the full raw child outputs preserved?

## Codex Review Findings

### Pass 1 (2026-05-23)

**P1 findings (incorporated):**
1. Interactive workflows can't be spawned as-is. Solution: purpose-built
   non-interactive phase agents.
2. "Phases are disk-isolated" is false at key boundaries. Solution:
   bundle-level delegation.

**P2 findings (incorporated):**
3. Dispatcher contract too weak. Solution: typed Phase Artifact Contract.
4. Swarm path must stay top-level in V1. Added as hard non-goal.
5. Skills access is not the real blocker. Purpose-built agents are the path.
6. Incremental rollout is bundle-by-bundle. Rollout order defined.
7. Deepen agent should own the merge atomically. See Deepen Ownership.

### Pass 2 (2026-05-23)

**Blocking fixes (incorporated):**
1. Run-id ordering regression -- run-id generation moved before Bundle 3
   so deepen agent can write to docs/reports/<run-id>/.
2. Returned manifests replaced with deterministic on-disk phase manifests.
   Agents write to known paths at phase start, update incrementally, and
   write final status before exiting. Git-log reconstruction demoted to
   emergency salvage only.

**Follow-up improvements (incorporated):**
3. Phase Artifact Contract strengthened with typed fields (phase_name,
   phase_status, brainstorm_path, plan_path, etc.) instead of generic lists.
4. Bundle 4 language strengthened -- compound is not proven disk-isolated
   enough to split from review/resolve in V1.
5. Rollout order changed -- Bundle 1 first to validate the harness, then
   Bundle 3 as first hard migration.

**New risk added:**
6. Maintenance drift -- phase agents duplicate workflow logic and can
   fall behind when upstream skills change. Mitigation: version tracking
   in phase agent headers + manual diff on plugin updates.

## Success Criteria

- The full autopilot pipeline (solo or swarm) completes without hitting
  context limits on builds that previously required /tail-resume
- All mandatory tail artifacts are produced in the same session
- No regression in artifact quality (solution docs, BUILD_TRACKING,
  self-audit reports remain at the same quality level)
- The orchestrator's peak context usage stays below 30k tokens for a
  typical 15-agent swarm build

## References

- Current autopilot: .claude/skills/autopilot/SKILL.md
- Context window optimization solution: docs/solutions/2026-05-20-autopilot-context-window-optimization.md
- Tail resume skill: .claude/skills/tail-resume/SKILL.md
- CHECKPOINT.md schema: defined in autopilot SKILL.md, Step "Context-Budget Checkpoint"
- Agent pitfalls: ~/.claude/docs/agent-pitfalls.md (59 failure classes)
- Codex handoff templates: ~/.claude/docs/codex-handoff-templates.md
- Workflow skills: ~/.claude/plugins/cache/every-marketplace/compound-engineering/2.35.2/commands/workflows/
