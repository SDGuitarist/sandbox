---
date: 2026-05-23
topic: autopilot-agent-delegation
status: complete
brief: docs/briefs/2026-05-23-autopilot-agent-delegation-brief.md
codex_reviews: 2
---

# Autopilot Agent Delegation Brainstorm

## What We're Building

Refactor the autopilot pipeline so each major phase (brainstorm, plan,
deepen, work, review) runs in its own spawned agent with its own context
window. The orchestrator becomes a thin dispatcher that reads deterministic
on-disk manifests between phases instead of accumulating 80-150k+ tokens
of inline output.

The goal is for the full autopilot pipeline (solo or swarm) to complete
without hitting context limits, eliminating the need for /tail-resume in
a separate session.

## Why This Approach

### Problem

The autopilot orchestrator runs every phase inline. Each phase adds 5-40k
tokens to context. By the time the shared tail starts (learnings, self-audit),
the context window is exhausted. The existing checkpoint gate (load > 30)
is a band-aid -- it only rescues the tail, not earlier phases.

### Why agent delegation over alternatives

Four options were evaluated pre-brainstorm:

1. **Session chaining (rejected)** -- Only rescues the tail. Doesn't solve
   exhaustion during work or review. Band-aid.
2. **Agent delegation (selected)** -- Addresses root cause. Each phase gets
   a full context window. Orchestrator stays adaptive.
3. **Shell script pipeline (rejected)** -- Loses adaptive orchestration.
   Each segment starts cold. Most reliable but least intelligent.
4. **Context pruning (deferred)** -- We don't control compression behavior.
   Could complement agent delegation later but isn't standalone.

### Why bundles, not individual phases

Codex review (Pass 1, P1 finding) identified that phases are NOT
independently delegatable. Some share in-memory state that cannot be
reconstructed from disk:

- Deepen + merge are coupled (merge needs deepening outputs in memory)
- Review + resolve + compound are coupled (compound needs fresh review context)

Delegation happens at the bundle level.

## Key Decisions

### 1. Five bundles, not eight individual phases

| Bundle | Phases | Coupling |
|--------|--------|----------|
| 1: Brainstorm | brainstorm + refinement | Disk-isolated (bundled for simplicity) |
| 2: Plan | plan + doc-review x2 | Disk-isolated (bundled for polish) |
| 3: Deepen | deepen + merge + audit | MUST be atomic (merge needs memory) |
| 4: Review | review + resolve + compound | MUST be bundled (compound needs context) |
| Solo work | work | Standalone |

### 2. Purpose-built non-interactive phase agents, not wrappers

Existing /workflows:* skills are interactive (ask questions, request approval).
We cannot wrap them in agents. Instead, we author new .claude/agents/phase-*.md
files that encode workflow logic directly with all interactive decisions
pre-resolved to autopilot defaults. The deepen-plan command already
demonstrates this pattern.

Each agent header includes a `# Source Workflows` comment with the plugin
version it was derived from (e.g., `compound-engineering/2.35.2`) to detect
maintenance drift when upstream workflows change.

### 3. Deterministic on-disk phase manifests

Every phase agent writes a YAML manifest to a known path at phase start
and updates it incrementally. The orchestrator reads the manifest after the
agent completes -- it never depends on agent return values for state.

Manifest lifecycle:
1. Agent creates manifest with `phase_status: IN_PROGRESS` at start
2. Agent updates fields as work progresses (commit hashes, artifact paths)
3. Agent writes `phase_status: PASS` or `FAIL` before exiting
4. Orchestrator reads manifest. If still `IN_PROGRESS`, agent died -- retry

Manifest paths (Bundles 1-2 write to `docs/reports/` before run-id exists;
Bundles 3-4 and solo work write under `docs/reports/<run-id>/` after run-id
generation):
- Bundle 1: `docs/reports/phase-brainstorm.manifest.yaml`
- Bundle 2: `docs/reports/phase-plan.manifest.yaml`
- Bundle 3: `docs/reports/<run-id>/phase-deepen.manifest.yaml`
- Bundle 4: `docs/reports/<run-id>/phase-review.manifest.yaml`
- Solo work: `docs/reports/<run-id>/phase-work.manifest.yaml`

### 4. Feed-Forward as a typed manifest field

Feed-Forward is not just buried in the prior phase's doc. The orchestrator
extracts the Feed-Forward block from each phase's manifest and injects it
into the next agent's prompt as typed fields:

```yaml
# In manifest
feed_forward:
  hardest_decision: "..."
  rejected_alternatives: "..."
  least_confident: "..."
```

The orchestrator injects into the next agent's prompt:
```
## Feed-Forward from previous phase (MUST address)
- Hardest decision: [value]
- Rejected alternatives: [value]
- Least confident: [value]
- Required follow-through: You must explicitly address this risk.
```

This makes the chain explicit, gives the orchestrator something concrete
to validate, and fits the acceptance-criteria model.

### 5. Deepen agent owns the merge atomically

The deepen phase agent spawns its research children, reconciles conflicts,
writes the canonical plan, and commits -- all in one atomic operation.
The orchestrator never sees raw research outputs.

Audit trail (full raw outputs + ledger):
- Raw child outputs: `docs/reports/<run-id>/deepen-raw/`
- Per-section merge ledger: `docs/reports/<run-id>/deepening-applied.md`
  (section, contributing agents, accepted changes, rejected changes, rationale)

Both are persisted because a ledger alone is self-reported and could
rationalize bad merge decisions. Raw outputs let reviewers verify.

### 6. Swarm coordination stays top-level (V1 non-goal)

Steps 7w-16w stay inline in the orchestrator. The non-tmux backend is
in-process -- teammates share the leader process. Wrapping swarm coordination
in a phase agent means all children die if the phase agent dies.

### 7. Rollout order: simplest first

1. Bundle 1 (brainstorm) -- validates the harness pattern end-to-end
2. Bundle 3 (deepen+merge) -- first coupled/hard migration
3. Bundle 2 (plan+doc-review) -- medium complexity
4. Bundle 4 (review+resolve+compound) -- heaviest, most coupled
5. Solo work -- standalone, can parallel with Bundle 4

### 8. Validation strategy: acceptance criteria + one-time side-by-side

**Ongoing:** A bundle passes if it writes expected artifacts to deterministic
paths, manifest is complete, next phase can consume outputs without
heuristics, all quality gates pass, and Feed-Forward is preserved.

**First rollout only:** Run same input through inline and delegated paths.
Compare for semantic equivalence, not textual equality. If no meaningful
regression, graduate to acceptance-criteria-only.

Per-bundle acceptance criteria:
- **Bundle 1:** Brainstorm doc in docs/brainstorms/ with Feed-Forward section,
  scope preserved from expanded brief, manifest complete.
- **Bundle 2:** Plan in docs/plans/ with frontmatter + Feed-Forward, carries
  forward brainstorm decisions, implementation-ready quality, manifest complete.
- **Bundle 3:** Canonical rewritten plan, deepening-applied.md + raw outputs
  in docs/reports/<run-id>/, repo in expected branch state, manifest complete.
- **Bundle 4:** Review artifacts + todo files in reports dir, fix commits
  applied, solution doc in docs/solutions/ with required sections, manifest
  complete.
- **Solo work:** Implementation commits passing verification, no interactive
  prompts, manifest complete.

### 9. Prompt size: test empirically on Bundle 1

No hard cap for V1. Phase agent prompts may reach 500+ lines when combining
workflow logic, CLAUDE.md rules, agent-pitfalls, plan content, and manifest
contract. The real risk is instruction-following degradation, not raw size.

Test Bundle 1 with full prompt shape. If the agent follows non-interactive
defaults, writes manifest correctly, and preserves Feed-Forward, the prompt
size is acceptable. If degradation occurs, introduce a soft cap and split
content into invariant global rules, bundle-specific workflow rules, and
current artifact inputs.

### 10. Maintenance drift is an accepted V1 tradeoff

Phase agents duplicate logic from /workflows:* skills. When upstream skills
change, phase agents can silently drift. Mitigation: version tracking in
agent headers + manual diff on plugin updates. Long-term: pre-flight check
comparing plugin version against agent version.

## Open Questions

None remaining. All four original open questions were resolved during
brainstorm dialogue:

1. Feed-Forward chain -> inject explicitly as typed manifest field
2. Testing strategy -> acceptance criteria + one-time side-by-side
3. Prompt size -> test empirically on Bundle 1
4. Deepen audit -> full raw outputs + per-section merge ledger

## Feed-Forward

- **Hardest decision:** Bundle boundaries. Determining which phases are
  truly coupled (must move together) vs. merely convenient to bundle
  required tracing in-memory state dependencies across the entire pipeline.
  Getting this wrong means either over-bundling (losing context savings)
  or under-bundling (broken handoffs).

- **Rejected alternatives:** (1) Session chaining -- only rescues the tail.
  (2) Shell script pipeline -- loses adaptive orchestration. (3) Individual
  phase delegation -- Codex identified coupling that forces bundles.
  (4) Wrapping existing interactive workflows -- P1 blocker, they ask
  questions that break zero-prompt. (5) Returned manifests -- Codex
  identified this conflicts with tail-resume's explicit-disk-state principle.

- **Least confident:** Whether compound can eventually be split from
  review+resolve (currently V1 non-negotiable bundle). The claim is that
  compound needs fresh review context, but this hasn't been empirically
  tested. If compound turns out to be disk-isolated, Bundle 4 could be
  split into two lighter agents in V2. The plan should verify this
  assumption during Bundle 4 rollout.
