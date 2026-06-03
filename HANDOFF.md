# HANDOFF — Sandbox (Autopilot Context-Death Solution)

**Date:** 2026-06-03
**Branch:** master
**Phase:** Plan COMPLETE → ready for **Work** phase

## Current State

The "Autopilot Context Death Solution" plan is finalized and committed
(`35b4950`, pushed to origin/master). It passed three review rounds:
1. Codex (round 1) — gaps/assumptions
2. Claude Code (round 2) — found 4 P1 + 5 P2, all fixed in-plan
3. Claude Code (round 3) — final consistency check, found 2 blockers, both fixed

The plan is a **meta-build**: it modifies the autopilot infrastructure itself
(SKILL.md + agent files), not an app. Plan frontmatter is `swarm: false`, so the
work phase is a manual/solo implementation in incremental commits — NOT an
autopilot run.

## What the Work Phase Implements

Three stages (plan §"Files Modified"):

- **Stage 1 — No-read discipline + output contracts**
  - SKILL.md: add `limit: 1` reads after phase reports (Steps 9w.5–9w.7 only);
    add the Phase Report Standardization rule; add Step 1.5 Phase Status section
    insertion; pass `build_tracking_path` to the two gate agents.
  - `spec-consistency-checker.md` + `spec-completeness-checker.md`: add Output
    Contract sections (write report STATUS line 1, write Phase Status row, end
    with `report_path:` + `STATUS:`).
- **Stage 2 — Deepening merge (swarm-only delegation)**
  - SKILL.md: move run-id to **Step 5.5** (before Step 6); add Step 6.03
    (swarm-only, spawn `deepen-merge-runner`), Step 6.03s (solo inline merge),
    Step 6.08 (commit self-review edits); remove old Step 6.5.
  - NEW `.claude/agents/deepen-merge-runner.md`.
- **Stage 3 — swarm-runner agent**
  - SKILL.md: replace inline Steps 11w–16w with a single swarm-runner spawn.
  - NEW `.claude/agents/swarm-runner.md` (assembly + inline verification +
    merge + cleanup).

## Two Round-3 Fixes — Do NOT Regress These

1. **Step 6.1 → 5.5 references (Item 4).** Run
   `grep -n "Step 6.1" .claude/skills/autopilot/SKILL.md` and update EVERY hit.
   Most become "Step 5.5". The exception is **Step 6.07's closing pointer**
   ("proceed to Step 6.1") which becomes **"proceed to Step 6.08"** — NOT 5.5.
   Also catch the CHECKPOINT.md template and Self-Audit step references.
2. **assembly-fix is unspawnable from swarm-runner (Finding B).** Sub-agents
   lack the Agent tool (spike confirmed). swarm-runner must resolve merge
   conflicts **inline** (step 3), with a blocking `merge-conflict:` FAIL if
   unresolvable. Do NOT add "spawn assembly-fix" anywhere in swarm-runner.
   The Stage 3 SKILL.md handler treats `contract-check:` and `merge-conflict:`
   as the two blocking failure classes (abort, set `final_status`, never reach
   the tail). assembly-fix is in Files NOT Modified.

## Suggested Implementation Order (incremental commits, ~50–100 lines each)

1. Stage 1 agent output contracts (2 agent files) — 1 commit.
2. Stage 1 SKILL.md no-read + Phase Status insertion + build_tracking_path — 1 commit.
3. Stage 2 step reordering (5.5 / 6.03 / 6.03s / 6.05 / 6.07 / 6.08) + all
   Step 6.1→5.5 reference updates — 1 commit.
4. `deepen-merge-runner.md` new file — 1 commit.
5. `swarm-runner.md` new file — 1 commit.
6. Stage 3 SKILL.md replacement of Steps 11w–16w + handler — 1 commit.

Commit BEFORE multi-file edits (mid-edit abort = no rollback).

## Verification (plan §Acceptance Tests / Verification Commands)

- `grep -n "Step 6.1" .claude/skills/autopilot/SKILL.md` → returns nothing after Stage 2.
- `head -1 docs/reports/<run-id>/*.md` → `STATUS:` on line 1 (no frontmatter).
- swarm-runner contract-check FAIL aborts pipeline (CLAUDE.md escalation rule);
  smoke/test FAIL continues to tail.
- Solo build trace: no `deepen-merge-runner`/`swarm-runner` spawn; Step 6.08 fires.

## Key Artifacts

| Item | Location |
|------|----------|
| Plan (FINAL) | docs/plans/2026-06-03-autopilot-context-death-solution-plan.md |
| Brainstorm | docs/brainstorms/2026-06-03-autopilot-context-death-solution-brainstorm.md |
| Spike (Agent-tool gap) | docs/reports/spike-nested-worktree-delegation.md |
| Review history | Plan §"Revision Changelog" (rounds 2 and 3) |
| Target: SKILL.md | .claude/skills/autopilot/SKILL.md |
| Target: tail-runner (reference only) | .claude/agents/tail-runner.md |

## Three Questions

1. **Hardest decision?** Whether Stage 2 (deepen-merge-runner) is worth keeping
   after the spike — kept swarm-only as a structural-consistency choice that
   saves ~0 context (orchestrator already carries deepening outputs). Real
   savings come from Stage 1 + Stage 3.
2. **What was rejected?** Delegating the deepening merge for solo builds, and
   modifying the three post-assembly checker agents (superseded by swarm-runner
   inlining their checks).
3. **Least confident about?** Whether reduced swarm-runner scope (Steps 11w–16w
   only; worker spawn stays inline) saves enough context for 20+ agent builds.
   The first 20+ agent build validates; `context_proxy_chars` is observability.

## Prior Context (still relevant)

Run 064 (Prompting Dashboard Engine) is complete. The `prompt-dashboard/` app
was built; working-tree currently shows those files deleted. If a NEW app build
starts later, clean up `prompt-dashboard/` ghost files first (FC48).

## Prompt for Next Session

```
Read HANDOFF.md and docs/plans/2026-06-03-autopilot-context-death-solution-plan.md.
This is the Work phase for the autopilot context-death solution — a manual,
incremental implementation (swarm: false, NOT an autopilot run). Implement the
three stages in the order listed in HANDOFF.md, one commit per step (~50–100
lines). Watch the two round-3 fixes: (1) update every "Step 6.1" reference,
with 6.07's pointer going to 6.08 not 5.5; (2) swarm-runner resolves merge
conflicts inline and never spawns assembly-fix. Start with Stage 1 agent output
contracts. Relevant files: .claude/skills/autopilot/SKILL.md,
.claude/agents/spec-consistency-checker.md, .claude/agents/spec-completeness-checker.md,
.claude/agents/tail-runner.md (delegation pattern reference).
```
