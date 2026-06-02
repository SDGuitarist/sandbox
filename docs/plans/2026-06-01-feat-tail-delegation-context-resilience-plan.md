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
| Solution doc | `docs/solutions/YYYY-MM-DD-<topic>.md` |
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

If the Edit tool fails (old_string not found), fall back to
`echo "| [N] | [role] | [commit_hash] | PASS |" >> BUILD_TRACKING.md`
and log a warning. Misplaced data is better than no data.
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

Wait for the agent to complete. Read its output and check for the
terminal STATUS line (PASS or FAIL).
```

#### Change C: Artifact verification (new Step 18w)

```
### Step 18w: Verify Tail Artifacts (SWARM ONLY — MANDATORY GATE)

After the tail-runner agent returns, verify these artifacts exist:

1. Solution doc: glob `docs/solutions/YYYY-MM-DD-*` for today's date.
   If missing: FAIL with "TAIL AGENT INCOMPLETE: Solution doc not written."

2. Self-audit report: read `<reports_dir>/self-audit.md`.
   If missing: FAIL with "TAIL AGENT INCOMPLETE: Self-audit not written."
   If STATUS contains FAIL: FAIL with the self-audit's error.

3. HANDOFF.md: read HANDOFF.md, check `**Date:**` contains today's date.
   If stale: FAIL with "TAIL AGENT INCOMPLETE: HANDOFF.md not updated."

4. BUILD_TRACKING.md: verify FAILURES and RUN_METRICS sections contain
   actual content (not placeholder comments like `<!-- Filled after review -->`).
   If empty: FAIL with "TAIL AGENT INCOMPLETE: BUILD_TRACKING not filled."

5. Learnings propagated: read the Update Log table at the bottom of
   `~/.claude/docs/agent-pitfalls.md`. The last row must contain today's
   date AND the current project name.
   If missing: FAIL with "TAIL AGENT INCOMPLETE: agent-pitfalls.md not updated."

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
- WHEN the tail-runner agent completes THE SYSTEM SHALL verify 5 artifacts: solution doc, self-audit, HANDOFF.md, BUILD_TRACKING, and agent-pitfalls.md Update Log
- WHEN all 5 artifacts pass verification THE SYSTEM SHALL output `<promise>DONE</promise>`
- WHEN the tail-runner agent returns THE SYSTEM SHALL parse its terminal STATUS line (PASS or FAIL)
- WHEN BUILD_TRACKING rows are written during assembly merge THE SYSTEM SHALL place them inside the AGENT_STATUS table (before the `---` separator), not at the end of the file
- WHEN a solo build reaches the Shared Tail THE SYSTEM SHALL run it inline with the existing Tier 1 checkpoint active

#### Error Cases
- WHEN the tail-runner agent crashes mid-execution THE SYSTEM SHALL detect missing artifacts in Step 18w and FAIL the run
- WHEN the tail-runner agent produces partial artifacts (solution doc but no self-audit) THE SYSTEM SHALL preserve partial commits and report the specific missing artifact
- WHEN an Edit tool call fails to match BUILD_TRACKING placeholder text THE SYSTEM SHALL fall back to `echo >>` append and log a warning
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

1. Create `.claude/agents/tail-runner.md` first (can be tested independently)
2. Apply Changes A-E to autopilot SKILL.md
3. Verify with grep/read that all `echo >> BUILD_TRACKING` patterns are gone

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

The agent MUST end with a parseable terminal line:
- On success: `STATUS: PASS — all tail artifacts written`
- On failure: `STATUS: FAIL — <specific reason>`

The orchestrator parses this line from the agent's return value.
```

## Sources & References

- **Origin brainstorm:** [docs/brainstorms/2026-06-01-tail-delegation-brainstorm.md](docs/brainstorms/2026-06-01-tail-delegation-brainstorm.md) — key decisions: delegation over checkpoint, agent definition file, Tier 1 stays for solo
- **Root cause analysis:** [docs/reports/061/context-death-analysis.md](docs/reports/061/context-death-analysis.md)
- **Original checkpoint design:** [docs/solutions/2026-05-20-autopilot-context-window-optimization.md](docs/solutions/2026-05-20-autopilot-context-window-optimization.md) — "Tier 2 pre-review resume" listed as future hardening
- **Agent definition exemplar:** `.claude/agents/spec-completeness-checker.md`
- **Autopilot skill:** `.claude/skills/autopilot/SKILL.md` (719 lines)

## Feed-Forward

- **Hardest decision:** Delegation over checkpointing. Both solve context
  death, but only delegation preserves uninterrupted execution.
- **Rejected alternatives:** Heuristic expansion (unreliable), split tail
  into two agents (YAGNI), auto-checkpoint (unnecessary file handoff),
  remove Tier 1 (unsafe for solo builds).
- **Least confident:** Whether `/workflows:review` and `/workflows:compound`
  work when invoked from inside a spawned agent. Test this first during
  implementation. Fallback: inline the logic in tail-runner.md.
