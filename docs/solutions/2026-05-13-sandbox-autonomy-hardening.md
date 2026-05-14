---
title: "Sandbox Autonomy Hardening"
date: 2026-05-13
tags: [autonomy, control-plane, autopilot, agent-pitfalls, spec-gate]
module: .claude/skills/autopilot
problem: "Autopilot tail steps were reminder-driven (skipped in 2/3 builds), control surface scope was undocumented, failure registry had duplicate IDs, and no pre-swarm spec consistency gate existed."
lesson: "Enforcement belongs in the skill (the execution engine), not in prose instructions or global hooks. Structural analysis beats single behavioral tests for proving non-deterministic interactions."
severity: P1
root_cause: "Four structural weaknesses: (1) FC11 -- learnings propagation was prose, not a gate. (2) No root operating contract separated local from global control surfaces. (3) Failure registry had duplicate FC13/FC14 from unsynchronized manual edits. (4) Spec contradictions could only be caught by humans post-assembly."
origin_plan: docs/plans/2026-05-13-feat-sandbox-autonomy-hardening-plan.md
related_prs: []
---

# Sandbox Autonomy Hardening

## Problem Statement

The sandbox autopilot system could run bounded autonomous builds but had four structural weaknesses that blocked higher autonomy:

1. **FC11 recurrence.** `/update-learnings` was skipped in 2 of 3 recent builds because it was a prose reminder, not a gate. The orchestrator mentally merged "compound" and "learnings" into one step and skipped the explicit propagation.
2. **Undocumented control surfaces.** No single file described which autonomy controls were project-local (skills, agents, settings) versus user-global (commands, hooks, agent-pitfalls). Agents entering the repo had to piece together policy from scattered skills and solution docs.
3. **Duplicate failure IDs.** FC13 and FC14 each appeared twice in agent-pitfalls.md. The Tunestamp build (May 6) added FC13/FC14, then the Lead-Scraper incidents (May 8-9) added different FC13/FC14 above them without checking for collisions.
4. **No pre-swarm spec consistency gate.** Cross-section contradictions (e.g., schema says `user_id`, route says `userId`) could only be caught by human structural verification after assembly.

## Root Cause

All four weaknesses shared one root cause: **enforcement was in prose, not in code.** CLAUDE.md said "run update-learnings." Solution docs said "check for duplicate IDs." The spec convergence loop doc said "human verification is non-optional." None of these were machine-enforced gates in the autopilot skill.

## Solution

Four phases, all scoped to the autopilot skill as the enforcement engine:

### Phase 1: Root Operating Contract (CLAUDE.md)

Created `~/Projects/sandbox/CLAUDE.md` with:
- Three autonomy classes (manual, autopilot-solo, autopilot-swarm)
- Forbidden actions with explicit out-of-repo write allowlist
- Required artifacts for completed runs
- Control surface scope table (project-local vs global)

**Key decision:** The contract explicitly documents that `/update-learnings-noninteractive` (autopilot) and `/update-learnings` (manual) write to 6 locations outside the repo during learnings propagation. Previous version claimed only agent-pitfalls.md was edited outside the repo.

### Phase 2: Hardened Autopilot Tail

**Spike result:** Structural analysis determined that the autopilot context cannot reliably suppress the `code-explainer` prompt in the global `/update-learnings` command. Evidence: FC11 shows the orchestrator skipped the entire step in 2/3 builds; competing instructions ("do not stop" vs "then ask") produce non-deterministic behavior; a single dry run would not be statistically significant.

**Path B chosen:** Created sandbox-local `/update-learnings-noninteractive` skill (292 lines) that reimplements Steps 0-6 without the interactive Step 7. The autopilot skill calls this instead of the global command.

**Four artifact gates added to the tail:**
1. Learnings Propagated table must appear in output
2. HANDOFF.md date must match today
3. Agent-pitfalls Update Log must have an entry for today's build
4. Agent-pitfalls IDs must be unique (no duplicates)

**BUILD_TRACKING.md completeness gate:** Required sections (AGENT_STATUS, FAILURES, RUN_METRICS) must be non-empty before the run is marked done.

### Phase 3: Failure Registry Normalization

**Freeze-and-assign strategy:** Numeric IDs are frozen forever. No renumbering.
- Duplicate FC13 ("Swarm Integration Wiring") reassigned to FC22
- Duplicate FC14 ("Anon RLS Enumeration") reassigned to FC23
- Semantic slugs added to all 23 classes (e.g., `{#fc13-testing-production-data}`)
- Reference table added at top of agent-pitfalls.md
- Autopilot skill now runs a uniqueness check as a mandatory gate

### Phase 4: Pre-Swarm Spec Consistency Gate

Created `spec-consistency-checker` agent that checks specs for cross-section contradictions before swarm launch. Runs at Step 9w.5 (after run-id generation and reports directory creation, before worker spawn).

Checks: schema vs route names, SQL vs app types, export vs import references, mock vs schema fields, wiring completeness. Produces PASS/FAIL report. FAIL blocks swarm launch.

**Key fix during review:** Original implementation had a sequencing bug (gate ran before run-id existed) and a tool mismatch (agent had read-only tools but needed to write the report). Both fixed in the review cycle.

## What Worked

| Pattern | Evidence |
|---------|----------|
| Enforcement in the skill, not in prose | 4 gates added, all scoped to autopilot skill only -- manual workflows unaffected |
| Structural analysis over behavioral testing | Spike correctly identified non-deterministic interaction without burning an expensive autopilot run |
| Freeze-and-assign for ID migration | Zero backward-compatibility breakage; all existing solution doc references (FC1, FC3, FC4, FC5, FC6, FC11) still valid |
| Plan-then-review-then-fix cycle | Codex review caught 4 real issues (tool mismatch, sequencing bug, CLAUDE.md inaccuracy, spike/plan misalignment) |
| Incremental commits | 6 commits, each under 100 lines changed, each independently reviewable |

## What to Watch

| Risk | Status | Mitigation |
|------|--------|------------|
| Autopilot skill complexity | 455 lines (45 under 500-line threshold) | Measure after each future phase; extract verification gates to helper skill if threshold crossed |
| Path B duplication | 292 lines duplicate global update-learnings Steps 0-6 | Deliberate technical debt; future plan should add `--no-prompt` flag to global command |
| Spec consistency gate untested in live swarm | Agent exists, sequencing verified, but no real swarm run yet | Next swarm build is the real test; seeded contradiction test is prescribed in verification plan |
| spec-contract-checker has same tool mismatch | Pre-existing issue, out of scope | Flag for future fix |

## Risk Resolution

| Flagged Risk | Status | Resolution |
|-------------|--------|------------|
| Autopilot skill complexity (Feed-Forward "least confident") | Controlled | Skill grew from 412 to 455 lines (+43). Well under 500-line threshold. Reordering during review fix actually reduced by 1 line. |
| Over-hardening manual workflows | Resolved | All gates scoped to autopilot skill only. Hooks remain reminders. Manual `/update-learnings` unchanged. |
| Global blast radius | Resolved | Only agent-pitfalls.md edited globally (additive). Global commands, hooks, settings verified untouched via md5/mtime checks. |
| Dual-source-of-truth | Resolved | No JSON manifest created. BUILD_TRACKING.md remains the single tracking artifact. |

## Stats

- **Commits:** 6 (5 work + 1 review fix)
- **Files changed:** 6 (1 new CLAUDE.md, 1 new skill, 1 new agent, 1 modified skill, 1 spike report, 1 plan)
- **Lines added:** 539 net
- **Review findings:** 4 from Codex (all fixed), 0 on second pass
- **Global file edits:** 1 (agent-pitfalls.md, additive only)

## Feed-Forward

- **Hardest decision:** Using structural analysis instead of a behavioral dry run for the Phase 2 spike. The plan originally prescribed a live autopilot build, but the structural evidence (FC11 history + competing instructions + statistical insignificance of a single run) was stronger than any single behavioral test. Updated the plan to accept this standard.
- **Rejected alternatives:** (1) Editing the global `update-learnings` command -- removed from the plan because it contradicted the "no global command edits" constraint. (2) Inlining Steps 0-6 into the autopilot skill -- rejected because it would push the skill past 600 lines. (3) Shifting duplicate FC IDs -- rejected because it breaks historical references. (4) Adding project-local hooks -- deferred because Claude Code doesn't currently support them and the autopilot skill is the right enforcement point.
- **Least confident:** Whether the 292-line duplication in `update-learnings-noninteractive` will diverge from the global command over time. If the global command adds new propagation targets, the sandbox-local copy won't pick them up automatically. The correct future fix is adding a `--no-prompt` flag to the global command, not maintaining two copies indefinitely.
