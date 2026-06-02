---
title: "feat: Tail Delegation for Autopilot Context Resilience"
type: feat
status: active
date: 2026-06-01
origin: docs/brainstorms/2026-06-01-tail-delegation-brainstorm.md
swarm: false
feed_forward:
  risk: "Whether the tail agent can effectively invoke /workflows:review and /workflows:compound as a spawned agent — architecturally supported but untested at this depth"
  verify_first: true
---

# feat: Tail Delegation for Autopilot Context Resilience

## Enhancement Summary

**Deepened on:** 2026-06-01
**Research agents used:** create-agent-skills, agent-native-architecture, learnings-researcher, architecture-strategist, pattern-recognition-specialist, code-simplicity-reviewer

### P1 Fixes Applied (3)
1. Added `tools` and `model` fields to tail-runner.md frontmatter template (pattern compliance)
2. Added 5th verification check to Step 18w: agent-pitfalls.md Update Log (learnings gap)
3. Added terminal STATUS line to tail-runner output contract (agent convention)

### P2 Improvements Applied (3)
1. Removed Change A (deepen-plan cap) — YAGNI, separate concern, unenforceable by instruction alone
2. Added Internal Variables section to agent template (explicit state tracking, no discovery heuristics)
3. Step 18w checks validate content, not just file presence (e.g., self-audit STATUS, BUILD_TRACKING placeholder detection)

### Codex Review Fixes Applied (6)
1. Added verify-first spike as mandatory Step 1 — prove Skill invocation works from spawned agent before committing to architecture
2. Strengthened Step 18w: WARN disposition, Run Quality Grade, deferred-risk HANDOFF linkage, "Learnings Propagated" table check
3. Removed echo >> fallback — retry with better anchor or fail loudly (fallback contradicts grep acceptance test)
4. Clarified branch precondition for Step 17w — tail-runner reviews merged main branch, not preserved failure branches
5. Added Remaining Risks section — pre-Step16w context pressure is unsolved (acceptable, monitor next 3-5 runs)
6. Exact solution_doc_path: tail-runner emits path, Step 18w verifies that file (no same-day glob)

## Overview

After the swarm build phase completes (Step 16w), the autopilot orchestrator
spawns a fresh agent to run the entire Shared Tail in a clean context window.
This eliminates context death during the tail without requiring human
intervention.

Two changes:

1. **Tail delegation** — new agent definition + autopilot SKILL.md spawn step
2. **BUILD_TRACKING structural fix** — `echo >>` → Edit tool for correct row placement

(see brainstorm: docs/brainstorms/2026-06-01-tail-delegation-brainstorm.md)

## What Exactly Is Changing?

### File 1: `.claude/agents/tail-runner.md` (NEW)

New agent definition containing the full Shared Tail workflow. The agent
receives run metadata as prompt parameters and executes all 10 tail steps:

1. Review (`/workflows:review`)
2. Resolve TODOs (`/compound-engineering:resolve_todo_parallel`)
3. Compound (`/workflows:compound`)
4. Update Learnings (`/update-learnings-noninteractive`)
5. Verify Learnings Artifacts (4 checks)
6. Fill FAILURES and RUN_METRICS in BUILD_TRACKING (swarm only)
7. Verify BUILD_TRACKING Completeness
8. Self-Audit (spawn self-audit-reviewer agent)
9. Verify Self-Audit (`/verify-self-audit`)
10. Update HANDOFF.md

**Inputs** (passed in prompt):

| Parameter | Source | Example |
|-----------|--------|---------|
| run_id | Step 6.1 | "061" |
| plan_path | Step 5 | "docs/plans/2026-06-01-...-plan.md" |
| reports_dir | Step 6.1 | "docs/reports/061/" |
| build_tracking_path | Step 1.5 | "BUILD_TRACKING.md" |
| project_name | Step 2 | "Prompting Dashboard Engine" |
| date | Runtime | "2026-06-01" |
| branch | Step 11w | "master" |
| feed_forward_risk | Plan frontmatter | "Claude API timeout..." |
| swarm_results | Steps 10w-16w | "10 agents, 0 conflicts, 13/13 smoke" |

**Internal state** (created during execution, not passed):

| Variable | Created at | Used by |
|----------|-----------|---------|
| solution_doc_path | Compound step (step 3) | Self-Audit step (step 8) |
| review_summary_path | Review step (step 1) | Self-Audit step (step 8) |
| p1_count, p2_count | Review step (step 1) | Fill BUILD_TRACKING (step 6) |
| fix_commits | Resolve TODOs (step 2) | Fill BUILD_TRACKING (step 6) |

**Key constraints:**

- Spawned as **foreground** (orchestrator waits for result)
- **No `isolation: "worktree"`** (operates on merged main branch)
- `mode: "bypassPermissions"`
- **No Tier 1 checkpoint** — if context fills, run fails. Recovery: manual
  completion of remaining steps. This is explicit, not an oversight.
- **Timeout: 30 minutes** — review + compound + learnings is heavier than
  a single swarm agent's 10-minute timeout
- **Feed-Forward**: review agents must scrutinize the plan's `feed_forward.risk`

**Output contract:**

The agent must produce all of these artifacts or the run fails:

| Artifact | Path |
|----------|------|
| Solution doc | `docs/solutions/YYYY-MM-DD-<topic>.md` (exact path emitted as `solution_doc_path` in output) |
| Self-audit report | `<reports_dir>/self-audit.md` |
| HANDOFF.md | `HANDOFF.md` (updated with today's date) |
| BUILD_TRACKING.md | FAILURES and RUN_METRICS sections filled |
| Learnings propagated | `~/.claude/docs/agent-pitfalls.md` updated |

### File 2: `.claude/skills/autopilot/SKILL.md` (MODIFY)

Five changes (A-E):

#### Change A: BUILD_TRACKING Edit-based writes (Steps 10.5w, 11w, 12w, 13w)

Replace all 5 `echo "..." >> BUILD_TRACKING.md` patterns with Edit tool
instructions. The Edit tool targets the correct insertion point (inside
the AGENT_STATUS table, before the `---` separator).

**Step 11w assembly merge** (primary fix — this is where run 061's rows
ended up misplaced):

Current:
```
echo "| [N] | [role] | [commit_hash] | PASS |" >> BUILD_TRACKING.md
```

New:
```
Use Edit tool to insert `| [N] | [role] | [commit_hash] | PASS |` as a
new row at the end of the AGENT_STATUS table. Target: the line immediately
before the `---` separator that follows the AGENT_STATUS section.

If the Edit tool fails (old_string not found): read BUILD_TRACKING.md to
find the correct anchor, then retry with the actual content. If the retry
also fails: FAIL with "BUILD_TRACKING EDIT FAILED: could not locate
AGENT_STATUS table separator." Do NOT fall back to echo >> — that
contradicts the structural fix and the grep acceptance test.
```

Same pattern for:
- Step 10.5w ownership gate: `echo "### Ownership Gate: ..."` → Edit insert
- Step 12w contract check: `echo "### Contract Check: ..."` → Edit insert
- Step 13w smoke test: `echo "### Smoke Test: ..."` → Edit insert
- Review append (Shared Tail): `echo "### Review: ..."` → Edit insert

**Edit target anchor:** All gate results (ownership, contract, smoke, review)
append after the last `|` row or `###` line in the AGENT_STATUS section,
before the `---` separator. The AGENT_STATUS table header written in
Step 1.5 provides the initial anchor.

#### Change B: Swarm tail delegation (new Step 17w)

After Step 16w (cleanup), add:

```
### Step 17w: Delegate Shared Tail (SWARM ONLY)

Use the **tail-runner** agent to execute the entire Shared Tail in a
fresh context window.

Pass these parameters in the prompt:
- run_id, plan_path, reports_dir, build_tracking_path
- project_name, date, branch
- feed_forward_risk (from plan frontmatter)
- swarm_results summary (agent count, FC37 rate, merge conflicts,
  smoke test results)

Spawn with `mode: "bypassPermissions"`. Do NOT set `isolation` or
`run_in_background` — the agent operates on the current branch and
the orchestrator must wait for its result.

**Branch precondition:** Before spawning, verify that HEAD is on the
expected branch (the one recorded in Step 11w). If Step 16w preserved
unmerged branches due to unresolved failures, the assembly branch was
still merged to main in Step 15w (verification failures are noted but
don't block the merge — see Steps 12w-14w "continue to review with
the failure noted"). The tail-runner reviews the merged code on the
main branch. Preserved branches exist only for manual inspection and
are NOT the review target.

If Step 15w did NOT merge (catastrophic failure — e.g., spec contract
check failed after retry), do NOT spawn the tail-runner. The run has
already failed at Step 14w. Step 17w is unreachable in this case.

Wait for the agent to complete. Read its output and check for the
terminal STATUS line (PASS or FAIL).
```

#### Change C: Artifact verification (new Step 18w)

```
### Step 18w: Verify Tail Artifacts (SWARM ONLY — MANDATORY GATE)

After the tail-runner agent returns, parse its terminal STATUS line.
If STATUS: FAIL, the run fails immediately with the agent's error.

Then verify these artifacts against CLAUDE.md Required Artifacts:

1. Solution doc: the tail-runner emits `solution_doc_path: <path>` in
   its output. Read that exact file. If the path is missing from output
   or the file doesn't exist: FAIL with "TAIL AGENT INCOMPLETE: Solution
   doc not written."

2. Self-audit report: read `<reports_dir>/self-audit.md`.
   If missing: FAIL with "TAIL AGENT INCOMPLETE: Self-audit not written."
   Validate required fields:
   - STATUS line exists and contains PASS
   - WARN disposition table exists and every WARN is disposed
   - Run Quality Grade section exists with 6 dimensions scored 1-5
   - Every DEFERRED disposition has a matching HANDOFF.md entry
   If any field is missing or invalid: FAIL with the specific deficiency.

3. HANDOFF.md: read HANDOFF.md, check `**Date:**` contains today's date.
   If stale: FAIL with "TAIL AGENT INCOMPLETE: HANDOFF.md not updated."
   Verify that every DEFERRED WARN from the self-audit has a
   corresponding entry in HANDOFF.md's Deferred Items section.

4. BUILD_TRACKING.md: verify FAILURES and RUN_METRICS sections contain
   actual content (not placeholder comments like `<!-- Filled after review -->`).
   If empty: FAIL with "TAIL AGENT INCOMPLETE: BUILD_TRACKING not filled."

5. Learnings propagation: verify BOTH:
   a. The Update Log table at the bottom of `~/.claude/docs/agent-pitfalls.md`
      has a row containing today's date AND the current project name.
   b. The tail-runner output contains the "Learnings Propagated" summary
      table (confirming /update-learnings-noninteractive completed).
   If either is missing: FAIL with "TAIL AGENT INCOMPLETE: learnings
   not propagated."

If ALL 5 pass: output `<promise>DONE</promise>` and stop.
If ANY fail: output the specific error. Do NOT silently accept.

Partial artifacts (e.g., solution doc exists but self-audit missing) are
preserved for manual recovery — do not revert commits.
```

#### Change D: Shared Tail delegation note

Add to the top of the existing Shared Tail section:

```
**Swarm builds:** Do NOT run the Shared Tail inline. Instead, proceed to
Step 17w (Delegate Shared Tail) which spawns the tail-runner agent.
The steps below only run inline for solo builds.
```

#### Change E: Remove Tier 1 checkpoint for swarm path

The Context-Budget Checkpoint (line ~618) currently applies to both paths.
With tail delegation, swarm builds never reach this code (they delegate
at Step 17w). Add a guard:

```
### Context-Budget Checkpoint — Pre-Audit (SOLO ONLY)

**Swarm builds skip this step** — the tail already runs in a fresh
agent context via Step 17w.
```

## What Must Not Change?

- Solo build path — Shared Tail stays inline, Tier 1 checkpoint stays active
- `/tail-resume` skill — unchanged, still works for solo build crash recovery
- Swarm agent spawning (Step 10w) — no changes to how work agents launch
- Pre-swarm gates (Steps 9w.5, 9w.6, 9w.7) — no changes
- Self-audit agent definition — no changes
- `update-learnings-noninteractive` skill — no changes

## How Will We Know It Worked?

### Acceptance Tests (EARS)

#### Happy Path
- WHEN a swarm build completes Step 16w THE SYSTEM SHALL spawn a tail-runner agent in foreground with all required parameters
- WHEN the tail-runner agent completes THE SYSTEM SHALL parse its emitted `solution_doc_path` and verify that exact file plus 4 other artifacts: self-audit (with WARN disposition + quality grade), HANDOFF.md (with deferred-risk linkage), BUILD_TRACKING, and agent-pitfalls.md Update Log
- WHEN all 5 artifacts pass verification THE SYSTEM SHALL output `<promise>DONE</promise>`
- WHEN the tail-runner agent returns THE SYSTEM SHALL parse its terminal STATUS line (PASS or FAIL)
- WHEN BUILD_TRACKING rows are written during assembly merge THE SYSTEM SHALL place them inside the AGENT_STATUS table (before the `---` separator), not at the end of the file
- WHEN a solo build reaches the Shared Tail THE SYSTEM SHALL run it inline with the existing Tier 1 checkpoint active

#### Error Cases
- WHEN the tail-runner agent crashes mid-execution THE SYSTEM SHALL detect missing artifacts in Step 18w and FAIL the run
- WHEN the tail-runner agent produces partial artifacts (solution doc but no self-audit) THE SYSTEM SHALL preserve partial commits and report the specific missing artifact
- WHEN an Edit tool call fails to match BUILD_TRACKING anchor text THE SYSTEM SHALL re-read the file, find the correct anchor, and retry once before failing loudly
- WHEN the tail-runner agent exceeds 30 minutes THE SYSTEM SHALL timeout and FAIL the run

#### Verification Commands
- Read `.claude/agents/tail-runner.md` — file exists with correct frontmatter
- Read `.claude/skills/autopilot/SKILL.md` — Step 17w and 18w exist
- Grep for `echo.*>>.*BUILD_TRACKING` in autopilot SKILL.md — should return 0 matches (all replaced with Edit tool instructions)
- Grep for `STATUS:` in `.claude/agents/tail-runner.md` — output contract includes terminal status line

## What Is the Most Likely Way This Plan Is Wrong?

The tail agent invoking `/workflows:review` and `/workflows:compound` as a
spawned agent. These are skills that themselves spawn multiple sub-agents.
Agents can use all tools (including the Skill tool), so this should work
architecturally. But it's untested at this depth — a skill invoking skills
inside a sub-agent. If it fails, the fallback is to inline the review and
compound logic directly in `tail-runner.md` rather than delegating to skills.

The Feed-Forward `verify_first` flag means the first thing to test during
implementation is whether `/workflows:review` works when invoked from inside
a spawned agent.

## Implementation Notes

### Order of changes

1. **Verify-first spike (MANDATORY before any other work):**
   Spawn a minimal test agent with `tools: Bash, Read, Skill` and
   `mode: "bypassPermissions"`. In its prompt, instruct it to:
   - Invoke `/workflows:review` on a trivial target (e.g., a single file)
   - Invoke `/workflows:compound` (can abort after it begins)
   - Invoke `/update-learnings-noninteractive`

   **If all three Skill invocations succeed:** proceed with the current
   design (tail-runner invokes skills directly).

   **If Skill invocations fail from inside a spawned agent:** revise the
   architecture. The orchestrator would invoke `/workflows:review`,
   `/workflows:compound`, and `/update-learnings-noninteractive` itself
   (before spawning the tail-runner), and the tail-runner would only
   handle artifact validation, BUILD_TRACKING fill, self-audit, and
   HANDOFF.md — the lightweight, disk-only steps that don't need skills.

   Document the spike result in `docs/reports/061/skill-invocation-spike.md`.

2. Create `.claude/agents/tail-runner.md` (design depends on spike result)
3. Apply Changes A-E to autopilot SKILL.md
4. Verify with grep/read that all `echo >> BUILD_TRACKING` patterns are gone

### Tail-runner.md structure

Follow the agent definition format from `.claude/agents/spec-completeness-checker.md`:

```markdown
---
name: tail-runner
description: Runs the complete Shared Tail (review through self-audit) in a fresh context window. Spawned by autopilot after swarm build completes.
tools: Bash, Read, Write, Edit, Grep, Glob, Skill
model: sonnet
---

## Role
[one paragraph]

## Inputs
[parameter table]

## Internal Variables
Track these as you execute — they are created during earlier steps and
used by later ones. Do NOT rely on discovery heuristics.

- `solution_doc_path` — set after Compound step writes the solution doc
- `review_summary_path` — set after Review step completes
- `p1_count`, `p2_count` — set after Review step completes
- `fix_commits` — set after Resolve TODOs step completes

## Steps
[numbered steps 1-10, each with clear instructions]

## Rules
[constraints: no checkpoint, 30min timeout, bypassPermissions for sub-agents]

## Output Contract
[artifact table + terminal status line]

The agent MUST end with parseable output:
- `solution_doc_path: <exact path to solution doc written>`
- `STATUS: PASS — all tail artifacts written`
  OR
- `STATUS: FAIL — <specific reason>`

The orchestrator parses `solution_doc_path` for exact file verification
in Step 18w (no same-day glob). The STATUS line determines pass/fail.
```

## Sources & References

- **Origin brainstorm:** [docs/brainstorms/2026-06-01-tail-delegation-brainstorm.md](docs/brainstorms/2026-06-01-tail-delegation-brainstorm.md) — key decisions: delegation over checkpoint, agent definition file, Tier 1 stays for solo
- **Root cause analysis:** [docs/reports/061/context-death-analysis.md](docs/reports/061/context-death-analysis.md)
- **Original checkpoint design:** [docs/solutions/2026-05-20-autopilot-context-window-optimization.md](docs/solutions/2026-05-20-autopilot-context-window-optimization.md) — "Tier 2 pre-review resume" listed as future hardening
- **Agent definition exemplar:** `.claude/agents/spec-completeness-checker.md`
- **Autopilot skill:** `.claude/skills/autopilot/SKILL.md` (719 lines)

## Remaining Risks

**Pre-Step 16w context pressure is unsolved.** Removing the deepen-plan
cap (YAGNI during deepening) means the orchestrator's context consumption
before the swarm build is unconstrained. Tail delegation solves the
post-build context problem (the tail runs in a fresh window), but if the
orchestrator runs out of context during Steps 1-16w themselves, the
pipeline still fails with no recovery path.

This is acceptable for now because:
1. The pre-swarm phases (brainstorm, plan, deepening, spec gates) have
   never caused context death — the problem has always been the tail.
2. If pre-swarm context death ever occurs, the fix is a separate
   "pre-swarm checkpoint" or deepen-plan cap — a different feature.
3. The tail delegation pattern can be extended to other phase boundaries
   if needed in the future.

This risk should be monitored across the next 3-5 swarm runs.

## Feed-Forward

- **Hardest decision:** Delegation over checkpointing. Both solve context
  death, but only delegation preserves uninterrupted execution.
- **Rejected alternatives:** Heuristic expansion (unreliable), split tail
  into two agents (YAGNI), auto-checkpoint (unnecessary file handoff),
  remove Tier 1 (unsafe for solo builds).
- **Least confident:** Whether `/workflows:review` and `/workflows:compound`
  work when invoked from inside a spawned agent. Test this first during
  implementation (verify-first spike, Step 1 of implementation order).
  Fallback: orchestrator runs skills, tail-runner handles artifacts only.
