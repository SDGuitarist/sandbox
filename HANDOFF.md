# HANDOFF — Sandbox (Autopilot Context-Death Solution)

**Date:** 2026-06-03
**Branch:** master
**Phase:** Work COMPLETE → ready for **Review** phase

## Current State

The "Autopilot Context Death Solution" Work phase is **complete and pushed**
to origin/master (6 commits, `40d6e64`..`f091760`). All three stages are
implemented across SKILL.md and two new agent files. Static verification
passed (see Verification below); runtime acceptance tests validate on the
first real swarm build.

This was a manual/solo meta-build (`swarm: false`) — it modifies the autopilot
infrastructure itself (SKILL.md + agent files), not an app. The plan
(`35b4950`) passed three pre-work review rounds (Codex + 2× Claude Code).

**Next phase = Review** (per compound loop): Codex first, apply fixes, then a
second Claude Code review. Scrutinize the plan's Feed-Forward "least confident"
item: whether the reduced swarm-runner scope (Steps 11w–16w only; worker spawn
stays inline) saves enough context for 20+ agent builds.

## Work Phase Commits (all on origin/master)

| Commit | Stage | What |
|--------|-------|------|
| `40d6e64` | S1 | Output contracts in spec-consistency-checker + spec-completeness-checker (STATUS→line 1, Phase Status row via Edit, +Edit tool, 3rd input arg) |
| `df1e4e5` | S1 | SKILL.md no-read (`limit:1` at 9w.5–9w.7), Phase Report Standardization rule, Step 1.5 Phase Status insertion, `build_tracking_path` to gates |
| `5abf122` | S2 | Reorder: 5.5 → 6 → 6.03/6.03s → 6.05/6.07 → 6.08; both round-3 fixes |
| `dce6267` | S2 | New `deepen-merge-runner.md` (swarm-only) |
| `7be76a9` | S3 | New `swarm-runner.md` (assembly + inline verification) |
| `f091760` | S3 | Delegate Steps 11w–16w to swarm-runner + blocking-failure handler |

## Verification Done (static)

- `grep "Step 6.1" SKILL.md` → empty (all → 5.5; CHECKPOINT template + self-audit caught)
- Step 6.07 control-flow pointer → `Step 6.08` (round-3 special case, NOT 5.5)
- Both new agent files exist; SKILL.md references swarm-runner in 14 places
- swarm-runner never spawns assembly-fix — resolves conflicts inline; two
  blocking classes (`contract-check:`, `merge-conflict:`); smoke/test non-blocking
- No orphaned `Step 6.5` / `Step 11w–16w` / stale-agent refs in `.claude/`

## Review-Phase Watch Items

- **No-Duplication Invariant** (plan §): confirm no same-path logic lives in
  both an agent file and SKILL.md inline. Solo merge (6.03s) is inline; swarm
  merge (6.03) is delegated — different paths, OK.
- **Deviations from plan I made (flag for reviewer):**
  1. Added `worker_status` to the swarm-runner spawn `Pass:` list in SKILL.md
     (the plan's agent spec requires it but its SKILL.md snippet omitted it).
  2. Made `assembly_branch`/`original_branch` values concrete in the spawn step.
  3. Updated the permission-mode allowlist + `fix_retries` metric + Step 17w
     branch-precondition to drop the now-superseded agents (not explicitly in
     the plan's change list, but required for consistency after delegation).
  4. Step 6.03s solo merge keeps Write-overwrite logic ("same as old 6.5"); the
     swarm path (deepen-merge-runner) uses per-correction Edit. Confirm both are intended.

## Prior Work Phase Plan (for reference)

The original Work-phase implementation notes follow below.

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
The Work phase is COMPLETE and pushed (6 commits, 40d6e64..f091760). This is the
Review phase for the autopilot context-death solution — a meta-build that changed
SKILL.md + two new agent files (deepen-merge-runner, swarm-runner). Diff to review:
`git diff 35b4950..f091760 -- .claude/`. Do Codex first, apply fixes, then a second
Claude Code review. Focus the plan's Feed-Forward "least confident" item (does the
reduced swarm-runner scope save enough context for 20+ agent builds) and the four
"Deviations from plan" flagged in HANDOFF. Verify the No-Duplication Invariant and
that the two round-3 fixes held (Step 6.1→5.5 with 6.07→6.08; swarm-runner never
spawns assembly-fix). Relevant files: .claude/skills/autopilot/SKILL.md,
.claude/agents/swarm-runner.md, .claude/agents/deepen-merge-runner.md,
.claude/agents/spec-consistency-checker.md, .claude/agents/spec-completeness-checker.md.
```
