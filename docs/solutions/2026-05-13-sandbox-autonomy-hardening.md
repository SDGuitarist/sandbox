---
title: "Sandbox Autonomy Hardening"
date: 2026-05-13
tags: [autonomy, control-plane, autopilot, agent-pitfalls, spec-gate, self-audit]
module: .claude/skills/autopilot
problem: "Autopilot tail steps were reminder-driven (skipped in 2/3 builds), control surface scope was undocumented, failure registry had duplicate IDs, no pre-swarm spec consistency gate existed, and no post-run self-audit verified the system's own documentation honesty."
lesson: "Enforcement belongs in the skill (the execution engine), not in prose instructions or global hooks. Structural analysis beats single behavioral tests for proving non-deterministic interactions. Self-audit gates must use stable keys, scope WARNs to current-run artifacts only, and extract verification logic into helper skills when the host file crosses its complexity budget."
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

### Phase 2b: Post-Run Self-Audit Layer (added 2026-05-14)

Added a self-audit step to the autopilot shared tail after BUILD_TRACKING verification and before Done. Three components:

**1. self-audit-reviewer agent** (215 lines): Reads all run artifacts, collects WARNs scoped to current-run sources only, assigns stable keys (`<run-id>-W<N>`), writes a canonical report with 7 sections: Final Run Status, WARN Disposition Table, Source Reconciliation, What Was Missed, Skeptical Reviewer Questions, Promotion Decisions, Unresolved Risk.

**2. verify-self-audit helper skill** (176 lines): 8 hard gates run after the agent produces its report. Extracted from the autopilot skill because Phase 2's gates pushed it past the 500-line complexity threshold.

**3. Solo path run-id** (Step 7s.0): Solo runs now generate a run-id and create `docs/reports/<run-id>/` so both paths share the same canonical report location.

**Key design decisions from 3 Codex review rounds:**
- WARNs scoped to current-run artifacts only (HANDOFF.md "Review Fixes Pending" is current-run; "Deferred Items (from prior work)" is excluded). Prevents clean runs from being downgraded by pre-existing project debt.
- Stable `<run-id>-W<N>` keys shared between self-audit.md and HANDOFF.md. Gate 3 greps for the exact key string instead of prose matching.
- Source Reconciliation table proves the agent scanned every report file. Gate 4 cross-checks the table against the actual directory listing.
- Gate 5 checks both directions: PIPELINE_PASS must have no deferred items; PIPELINE_PASS_WITH_DEFERRED_RISK must have a non-empty Unresolved Risk section.
- Gate 6 enforces section completeness: What Was Missed exists, at least 3 skeptical questions, at least 1 promotion decision row.

## What Worked

| Pattern | Evidence |
|---------|----------|
| Enforcement in the skill, not in prose | 4 tail gates + 8 self-audit gates, all scoped to autopilot skill -- manual workflows unaffected |
| Structural analysis over behavioral testing | Spike correctly identified non-deterministic interaction without burning an expensive autopilot run |
| Freeze-and-assign for ID migration | Zero backward-compatibility breakage; all existing solution doc references (FC1, FC3, FC4, FC5, FC6, FC11) still valid |
| Iterative Codex review cycle | 3 rounds on self-audit: round 1 found 5 issues (2 High), round 2 found 4 issues, round 3 LGTM. Each round made the gates more precise. |
| Extract when complexity budget triggers | Autopilot skill hit 516 lines; extracted verify-self-audit helper skill, brought it to 498 |
| Stable keys over prose matching | `<run-id>-W<N>` keys eliminated false positives from wording drift between self-audit and HANDOFF.md |
| Current-run scoping | Excluding pre-existing HANDOFF debt from WARN collection prevents clean builds from inheriting prior debt |

## What to Watch

| Risk | Status | Mitigation |
|------|--------|------------|
| Autopilot skill complexity | 498 lines (extraction triggered at 516, brought under 500) | verify-self-audit helper absorbed the overflow. Future additions may need further extraction. |
| Path B duplication | 292 lines duplicate global update-learnings Steps 0-6 | Deliberate technical debt; future plan should add `--no-prompt` flag to global command |
| WARN scope coupled to HANDOFF section names | Agent references exact names "Review Fixes Pending (P2)" and "Deferred Items (from prior work)" | If HANDOFF.md is reformatted, update agent-reviewer lines 41/50 |
| Gate 6 "What Was Missed" check is lenient | Presence check only; rubber-stamp "no omissions found" passes | Acceptable: external gates catch structure, agent judgment handles content quality |
| Self-audit untested in live build | Agent + gates exist, 3 Codex reviews passed, but no real autopilot run yet | Next autopilot build is the real test |

## Risk Resolution

| Flagged Risk | Status | Resolution |
|-------------|--------|------------|
| Autopilot skill complexity (Feed-Forward "least confident") | Resolved | Skill hit 516 lines when self-audit gates were inlined. Plan's mitigation triggered: extracted verify-self-audit helper skill (176 lines). Autopilot now 498 lines. |
| Over-hardening manual workflows | Resolved | All gates scoped to autopilot skill only. Hooks remain reminders. Manual `/update-learnings` unchanged. |
| Global blast radius | Resolved | Only agent-pitfalls.md edited globally (additive). Global commands, hooks, settings verified untouched via md5/mtime checks. |
| Dual-source-of-truth | Resolved | No JSON manifest created. BUILD_TRACKING.md remains the single tracking artifact. |
| False-positive gate risk (self-audit) | Resolved | 3 Codex rounds: (1) stable keys replaced prose matching, (2) current-run scoping excluded pre-existing debt, (3) Gate 2 validates key format/disposition enum. |

## Stats

- **Commits:** 7 (5 work + 1 review fix + 1 self-audit layer)
- **Files changed:** 8 (1 new CLAUDE.md, 2 new skills, 2 new agents, 1 modified skill, 1 spike report, 1 plan)
- **Lines added:** 976 net (539 original + 437 self-audit layer)
- **Review findings:** Phases 1-4: 4 from Codex (all fixed). Self-audit: 5 round 1 + 4 round 2 + LGTM round 3.
- **Global file edits:** 1 (agent-pitfalls.md, additive only)

## Feed-Forward

- **Hardest decision:** Using structural analysis instead of a behavioral dry run for the Phase 2 spike. The plan originally prescribed a live autopilot build, but the structural evidence (FC11 history + competing instructions + statistical insignificance of a single run) was stronger than any single behavioral test. For the self-audit, the hardest call was scoping WARNs to current-run only -- it required 3 Codex rounds to get the boundary right (pre-existing HANDOFF debt was contaminating clean builds).
- **Rejected alternatives:** (1) Editing the global `update-learnings` command -- contradicted "no global edits" constraint. (2) Inlining Steps 0-6 into the autopilot skill -- would push past 600 lines. (3) Shifting duplicate FC IDs -- breaks historical references. (4) Prose matching for deferred items between self-audit and HANDOFF -- replaced by stable `<run-id>-W<N>` keys after Codex round 1 found it was a false-positive risk. (5) Keeping all 8 self-audit gates inline in the autopilot skill -- extraction triggered by the plan's own 500-line mitigation.
- **Least confident:** Whether the self-audit agent will produce consistently high-quality "What Was Missed" and "Skeptical Questions" sections across varying build complexity. Gate 6 checks presence but not substance. The first few real builds will reveal whether the agent's judgment is reliable or whether tighter structural checks are needed.
