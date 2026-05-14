---
title: "feat: Sandbox Autonomy Hardening"
type: feat
status: refined
date: 2026-05-13
origin: "2026-05-13 sandbox autonomy analysis"
build_method: manual
swarm: false
feed_forward:
  risk: "Phase 0 resolved: commands and hooks are global-only and are never edited by this plan. The remaining risk is autopilot skill complexity — concentrating all enforcement in one file that is already 413 lines. If Phase 2 Path B is needed, a second skill file absorbs the duplication cost instead of inflating the autopilot skill."
  verify_first: true
---

# feat: Sandbox Autonomy Hardening

## Plan Quality Gate

### 1. What exactly is changing?

Five changes, in this order:

1. **Resolve control-plane scope** by documenting which autonomy controls are project-local versus user-global, based on actual Claude Code override behavior (Phase 0 — already resolved during plan review).
2. **Add a sandbox root operating contract** so the repo has one authoritative file describing allowed autonomy classes, escalation thresholds, and required artifacts.
3. **Harden the autopilot tail** so mandatory steps are machine-enforced and non-interactive during unattended runs.
4. **Normalize the failure registry** so agent memory has stable IDs and cannot drift through duplicate numbering.
5. **Add a pre-swarm spec consistency gate** that checks cross-section contradictions before worker agents launch.

### 2. What must NOT change?

- Existing product app behavior in sandbox subprojects unless a change is required to support the autonomy control plane.
- The core compound loop itself: plan, work, review, compound, and learnings propagation remain the workflow.
- Manual learning flows outside autopilot. `code-explainer` can remain available when explicitly requested.
- Other repos on this machine unless a change is explicitly intended to be global and documented as such.
- Current production-safety rules around deadline pressure, manual-review math, and DB safety in sensitive repos like `lead-scraper`.
- Global hooks and commands — no edits to files in `~/.claude/hooks/` or `~/.claude/commands/`. All behavioral changes must be sandbox-local or via the autopilot skill.
- Global docs (`~/.claude/docs/`) — only `agent-pitfalls.md` is edited (Phase 3), and only with additive changes (new IDs for duplicates, semantic slugs, reference table). This is intentional and documented in Phase 3's blast radius note.

### 3. How will we know it worked?

See [Acceptance Tests](#acceptance-tests) below for EARS-format criteria and verification commands.

### 4. What is the most likely way this plan is wrong?

Three risks:

1. **Over-hardening risk.** Turning reminders into blockers could make normal manual work frustrating if the gates are not limited to autopilot or work-phase contexts. Mitigation: all blocking behavior is scoped to the autopilot skill, not hooks.
2. **Dual-source-of-truth risk.** BUILD_TRACKING.md already exists as a concept. Adding a separate manifest.json would create confusion about which is authoritative. Resolution: BUILD_TRACKING.md stays as the single tracking artifact; add a structured JSON block to it rather than creating a parallel system.
3. **Spec gate false positives.** A pre-swarm consistency checker could block valid builds on ambiguous matches. Mitigation: the gate produces a report with explicit pass/fail items; ambiguous matches are flagged but don't block unless they match known contradiction patterns.

## Acceptance Tests

### Happy Path
- WHEN the autopilot skill is invoked in sandbox THEN the system SHALL complete all tail steps (learnings propagation, agent-pitfalls verification, BUILD_TRACKING update) without interactive pauses
- WHEN a new agent enters the sandbox repo THEN the system SHALL provide a root CLAUDE.md that describes allowed autonomy classes, forbidden actions, and required artifacts
- WHEN a swarm build spec contains a cross-section contradiction (e.g., schema field referenced but not defined) THEN the system SHALL block swarm launch with a FAIL report before Step 10w
- WHEN agent-pitfalls.md is read THEN the system SHALL contain zero duplicate failure class IDs

### Error Cases
- WHEN the autopilot tail is missing a required artifact (e.g., no learnings propagation) THEN the system SHALL fail the run with a clear error message rather than silently succeeding
- WHEN a pre-swarm spec check encounters an ambiguous match THEN the system SHALL flag it as a warning without blocking launch

### Verification Commands

**Phase 1 — Root contract:**
- `head -20 /Users/alejandroguillen/Projects/sandbox/CLAUDE.md` — exists and opens with autonomy class definitions
- `grep -c "autopilot-solo\|autopilot-swarm\|manual" /Users/alejandroguillen/Projects/sandbox/CLAUDE.md` — returns 3+ (all classes documented)

**Phase 2 — Unattended tail:**
- `cat docs/reports/spike-update-learnings-noninteractive.md` — spike artifact exists and records the decision path chosen
- Solo dry-run behavioral test: run a trivial autopilot build end-to-end; capture output; `grep -c "Want to run code-explainer" <output>` must return 0
- `grep -c "FAIL\|fails the run" /Users/alejandroguillen/Projects/sandbox/.claude/skills/autopilot/SKILL.md` — confirms artifact gates exist (should be higher than current count)

**Phase 3 — Failure registry integrity:**
- `grep -oP '## Failure Class \K\d+' ~/.claude/docs/agent-pitfalls.md | sort -n | uniq -d` — must return empty (no duplicate numeric IDs)
- `grep -c '{#fc' ~/.claude/docs/agent-pitfalls.md` — returns 23 (every class has a semantic slug)
- `grep -c '## Failure Class 22\|## Failure Class 23' ~/.claude/docs/agent-pitfalls.md` — returns 2 (duplicates were reassigned, not deleted)

**Phase 4 — Pre-swarm spec gate:**
- `ls /Users/alejandroguillen/Projects/sandbox/.claude/agents/spec-consistency-checker.md` — agent definition exists
- Seeded contradiction test: create a spec with `user_id` in schema and `userId` in route params; run the gate agent; verify output contains FAIL

## Overview

Sandbox already has the right autonomy architecture:

- shared-spec-first planning
- swarm ownership boundaries
- verification agents after assembly
- solution docs and lessons compounding into future runs

What it lacks is a fully hardened control plane. Today, some critical behaviors still depend on reminders, prose instructions, or global files whose scope is unclear. The next step is not "more powerful agents." The next step is making the autonomy layer more deterministic, inspectable, and safely scoped.

## Problem Statement / Motivation

The current setup can successfully run bounded autonomous builds, but it still has four structural weaknesses:

1. **Mandatory steps are not always enforced.** The system has already documented repeated failures where learnings propagation or tracking artifacts were skipped because they were reminder-driven rather than gate-driven.
2. **Control surfaces are split across scopes.** Sandbox uses project-local skills and agent memory, but also depends on user-global commands, hooks, and settings. This creates uncertainty about blast radius.
3. **System memory is at risk of drift.** The failure registry is valuable, but duplicate numeric IDs (both FC13 and FC14 appear twice) prove it is being maintained manually without a stable identity scheme.
4. **Cross-section spec contradictions slip through.** The spec convergence loop catches many issues but relies on human structural verification. A machine-checkable gate would catch the mechanical contradictions before humans review semantics.

If the goal is higher autonomy, these weaknesses must be fixed before expanding agent authority.

## Non-Goals

- Rewriting the compound engineering workflow from scratch
- Replacing solution docs, `HANDOFF.md`, or `LESSONS_LEARNED.md`
- Moving all repo logic into global Claude configuration
- Making production-sensitive repos fully unattended by default
- Optimizing for speed over recoverability
- Creating a separate JSON manifest system (BUILD_TRACKING.md is sufficient)
- Adding safety profiles to run scripts (existing Docker isolation already handles this)

## Phase 0: Control Surface Decision Record (RESOLVED)

Research during plan review confirmed the following scope model. No implementation starts without this being explicit.

### Repo-Local Authority Surfaces (sandbox owns these)

| Surface | Path | Override mechanism |
|---------|------|--------------------|
| Settings | `.claude/settings.local.json` | Project-level settings supersede global |
| Skills | `.claude/skills/autopilot/`, `.claude/skills/resolve-todos/` | Project skills invoked by name |
| Agents | `.claude/agents/` (6 agents) | Project-scoped, used only in sandbox builds |
| Agent memory | `.claude/agent-memory/` | Per-agent state within project |
| Root contract | `CLAUDE.md` (to be created) | Project CLAUDE.md layers on top of global |

### Global Authority Surfaces (sandbox cannot override these)

| Surface | Path | Why global |
|---------|------|-----------|
| Commands | `~/.claude/commands/update-learnings.md` | No project-local command override mechanism in use |
| Hooks | `~/.claude/hooks/` (8 hooks) | Hook definitions in global `settings.json`; no project-local hooks exist |
| Permissions | `~/.claude/settings.json` (36 auto-allow patterns) | Base permission layer |
| Agent pitfalls | `~/.claude/docs/agent-pitfalls.md` | Cross-project failure registry by design |
| Tracking template | `~/.claude/docs/autopilot-tracking-template.md` | Template, not instance |

### Scope Decisions

1. **`update-learnings` stays global and unmodified.** The autopilot skill already calls it as a step. Phase 2's spike will determine whether the autopilot context naturally suppresses the `code-explainer` prompt (Path A) or whether a sandbox-local non-interactive skill is needed as a replacement (Path B). Neither path edits the global command.
2. **`agent-pitfalls.md` stays global by design.** It is a cross-project failure registry. Sandbox references it but does not own it. When sandbox discovers new failure classes, they are appended to the global file (this is the intended update path).
3. **Hooks stay global.** Sandbox does not need project-local hooks. The autopilot skill is the enforcement engine; hooks provide reminders for manual work across all repos.
4. **New enforcement goes into the autopilot skill**, not into hooks or global commands. This keeps blast radius contained.

### Deferred

- Project-local hooks (Claude Code may support this in future; not needed now)
- Project-local command overrides (`.claude/commands/` exists but is unused)

## Phase 1: Add a Sandbox Root Operating Contract

### Goal

Create a root `CLAUDE.md` for sandbox that acts as the top-level contract for agents entering this repo.

### Contents

- allowed autonomy classes (`manual`, `autopilot-solo`, `autopilot-swarm`)
- forbidden actions (no production DB access, no force-push, no external API calls without declaration)
- production-safety assumptions
- required artifacts for completed runs (BUILD_TRACKING.md, solution doc, learnings propagation)
- escalation rules
- review expectations
- scope notes: "Commands, hooks, and agent-pitfalls are global. Skills, agents, and settings are project-local."

### Files

- **Create (repo-local):** `/Users/alejandroguillen/Projects/sandbox/CLAUDE.md`

### Success criteria

- A new agent can understand the sandbox operating model from one root file.
- Repo policy is no longer spread only across skills, hooks, and old solution docs.

## Phase 2: Harden the Autopilot Tail

### Goal

Remove interactive pauses and enforce mandatory tail steps within the autopilot skill.

### Pre-Implementation Spike: update-learnings Non-Interactive Behavior

The global `update-learnings` command (Step 7, line 263 of `~/.claude/commands/update-learnings.md`) explicitly says: *"Then ask: Want to run code-explainer to deepen your understanding of what was just solved?"* The autopilot skill calls `/update-learnings` at its tail step. The question is whether the autopilot skill's surrounding context ("do not stop between steps", "do not wait for user input") reliably suppresses this prompt.

**Spike procedure:**

1. Run a solo autopilot build on a trivial app (e.g., a single-file Flask hello-world).
2. Capture the full output of the `Update Learnings` tail step.
3. Check whether the string "code-explainer" appears as an interactive question in the output.

**Success artifact:** A file `docs/reports/spike-update-learnings-noninteractive.md` containing:
- The captured tail-step output (or a relevant excerpt)
- Whether the code-explainer question appeared (YES/NO)
- Which implementation path was chosen (see decision gate below)

**Decision gate (choose exactly one — both paths are sandbox-local):**

| Spike result | Implementation path |
|---|---|
| Autopilot context reliably suppresses the prompt | **Path A:** No code change to any file. Add a comment in the autopilot skill documenting why this works and a regression check in the verification step. |
| Prompt still appears despite autopilot context | **Path B:** Create a sandbox-local skill `.claude/skills/update-learnings-noninteractive/SKILL.md` that reimplements Steps 1-6 of the global `update-learnings` command without Step 7 (the code-explainer prompt). The autopilot skill calls `/update-learnings-noninteractive` instead of `/update-learnings`. This duplicates propagation logic but keeps all changes sandbox-local and avoids inflating the autopilot SKILL.md (the new skill is a separate file). The global `update-learnings` command is never modified. |

**Note:** A previous version of this plan included a third path that edited the global `update-learnings.md` command. That path was removed because it contradicted the "must not change global commands" constraint. If Path B's duplication becomes a maintenance burden, the correct response is a future plan to refactor the global command — not a silent global edit from this plan.

**The spike must complete before any other Phase 2 work begins.** The rest of Phase 2 applies regardless of which path is chosen.

### Main changes (after spike)

1. **Suppress the `code-explainer` prompt** via the path chosen in the decision gate above.
2. **Add artifact existence checks** after the update-learnings step. The autopilot tail must verify:
   - The "Learnings Propagated" summary table was output (proves Steps 1-6 ran)
   - `HANDOFF.md` was updated (timestamp matches today)
   - The agent-pitfalls Update Log has an entry for today's build
   If any check fails, the run fails with a specific error naming the missing artifact.
3. **Add a BUILD_TRACKING.md completeness check** before marking the run as done. Required sections: AGENT_STATUS, FAILURES, RUN_METRICS. If any section is empty or missing, the run fails.

### Files

- **Edit (repo-local):** `/Users/alejandroguillen/Projects/sandbox/.claude/skills/autopilot/SKILL.md` — both paths
- **Create (repo-local, Path B only):** `/Users/alejandroguillen/Projects/sandbox/.claude/skills/update-learnings-noninteractive/SKILL.md` — sandbox-local non-interactive variant
- **Create (repo-local):** `docs/reports/spike-update-learnings-noninteractive.md` — spike result artifact

### What this does NOT change

- The global `update-learnings` command (`~/.claude/commands/update-learnings.md`) — never edited by any path.
- Global hooks — they remain reminders, not blockers.
- Manual workflows — `code-explainer` is still available when a human calls `/update-learnings` directly.

### Guardrails

- Blocking behavior is scoped to the autopilot skill only.
- The spike determines the mechanism; no implementation proceeds on an assumption.

### Success criteria

- The spike artifact exists and records the decision.
- Autopilot can finish unattended without the `code-explainer` question appearing as an interactive pause.
- Missing learnings propagation, missing HANDOFF.md update, or missing agent-pitfalls log entry fails the run.
- Missing BUILD_TRACKING.md sections fail the run.

## Phase 3: Normalize the Failure Registry

### Goal

Stabilize agent memory so references to past failure classes stay durable.

### Current state (from plan review research)

Two duplicate IDs exist:
- **FC13** appears at line ~186 ("Testing Against Production Data") AND line ~234 ("Swarm Agents Build Components But Skip Integration Wiring")
- **FC14** appears at line ~198 ("executescript() With Destructive DDL") AND line ~250 ("Anon RLS Policy Enables Table Enumeration")

Existing solution docs reference FC1, FC3, FC4, FC5, FC6, FC11 — all from the first batch (lines 10-162), so they are not affected by the duplicates.

### Migration strategy: freeze and assign

**Rule: numeric IDs are frozen. No renumbering, ever.** This prevents historical references from breaking.

1. **Keep FC1-FC14 (first occurrences, lines 10-198) unchanged.** These are the original definitions.
2. **Assign new IDs to the duplicates at the end of the sequence:**
   - Line ~234 "Swarm Agents Build Components But Skip Integration Wiring" → **FC22** (next available after current FC21)
   - Line ~250 "Anon RLS Policy Enables Table Enumeration" → **FC23**
3. **FC15-FC21 keep their current numbers.** They are already unique.
4. **Add a semantic slug to every class heading** as the durable identifier going forward. Format: `## Failure Class 13: Testing Against Production Data {#fc13-testing-production-data}`. The slug is the primary reference for new solution docs; the numeric ID is a legacy index.
5. **Add a reference table** at the top of the file mapping all IDs to names, so agents can look up a class without scanning the full document.

### Why not shift IDs?

Shifting FC15-FC21 down by two would make every existing reference to those classes (in solution docs, BUILD_TRACKING files, agent-pitfalls citations in SKILL.md) point to the wrong definition. The fix would be worse than the bug.

### Files

- **Edit (global):** `~/.claude/docs/agent-pitfalls.md` — fix duplicates (assign FC22/FC23), add semantic slugs, add reference table
- **Edit (repo-local):** `/Users/alejandroguillen/Projects/sandbox/.claude/skills/autopilot/SKILL.md` — add uniqueness check to the "Verify Agent Pitfalls Updated" gate

### Uniqueness check implementation

Add to the autopilot skill's "Verify Agent Pitfalls Updated" step:

```
After confirming the Update Log entry, extract all Failure Class numbers:
  grep -oP '## Failure Class \K\d+' ~/.claude/docs/agent-pitfalls.md | sort -n | uniq -d
If this returns any output, FAIL with: "DUPLICATE FAILURE CLASS IDs DETECTED: [list]. Fix before proceeding."
```

### Blast radius note

Editing `agent-pitfalls.md` is a global change. This is intentional — the duplicates affect all repos. The changes are:
- Two headings get new numbers (additive)
- Semantic slugs added to all headings (additive)
- Reference table added at top (additive)
- No existing content is removed or renumbered

### Success criteria

- `grep -oP '## Failure Class \K\d+' ~/.claude/docs/agent-pitfalls.md | sort -n | uniq -d` returns empty.
- Every failure class has a numeric ID AND a semantic slug.
- The autopilot skill's pitfalls gate catches future duplicates automatically.
- All existing solution doc references (FC1, FC3, FC4, FC5, FC6, FC11) still point to the correct definitions.

## Phase 4: Add a Pre-Swarm Spec Consistency Gate

### Goal

Catch mechanical contradictions in specs before swarm workers launch.

### Relationship to existing spec convergence loop

The spec convergence loop (Codex + NotebookLM + human) catches semantic and structural issues. This gate catches **mechanical** contradictions that are machine-checkable:

- schema fields referenced but not defined
- SQL types versus app-layer types
- RPC parameter names versus caller argument names
- promised route methods versus actual route table entries
- mock/fixture outputs versus declared schemas

This gate runs **after** plan deepening and **before** worker spawn — it is a final machine check, not a replacement for the human convergence loop.

### Implementation

Create a **new** agent, not an extension of the existing `spec-contract-checker.md`. The two agents have different jobs at different stages:

| Agent | Runs when | Checks what | Input |
|-------|-----------|-------------|-------|
| `spec-contract-checker.md` (existing) | Step 12w, after assembly | Assembled CODE matches SPEC interfaces | Code + spec |
| `spec-consistency-checker.md` (new) | Between Step 7 and Step 10w, before swarm launch | SPEC is internally consistent across sections | Spec only |

- **Create (repo-local):** `/Users/alejandroguillen/Projects/sandbox/.claude/agents/spec-consistency-checker.md` — new pre-swarm agent
- **Edit (repo-local):** `/Users/alejandroguillen/Projects/sandbox/.claude/skills/autopilot/SKILL.md` — add gate between plan deepening and swarm spawn (swarm path only; solo path does not need this gate)

### Gate behavior

- Produces a structured PASS/FAIL report
- FAIL with unresolved contradictions blocks swarm launch
- Ambiguous matches are flagged as warnings, not blockers

### Success criteria

- A seeded cross-section contradiction (e.g., spec references `user_id` but schema defines `userId`) fails before Step 10w.
- The gate catches issues that the existing contract checker would miss because they span spec sections, not just interface boundaries.

## Deferred: Safety Profiles

The original plan included a Phase 6 for defining named execution profiles (`offline-safe`, `online-build`, `prod-sensitive`). This is **deferred** because:

- The existing run scripts (`run-autopilot-safe.sh`, `run-autopilot.sh`, `run-autopilot-full.sh`) already implement three distinct safety levels at the Docker layer.
- Adding a formal profile system on top would be speculative infrastructure without a current need.
- If profiles become necessary, they should be designed after several more builds reveal what the Docker-layer isolation doesn't cover.

## Recommended Execution Order

1. **Phase 1:** Add root `CLAUDE.md` (sets the contract for everything else)
2. **Phase 2:** Harden autopilot tail (highest-impact change for unattended reliability)
3. **Phase 3:** Normalize failure registry (fixes a known data integrity issue)
4. **Phase 4:** Add pre-swarm spec consistency gate (extends the autonomy boundary)

Phase 0 is resolved — the control surface decision record is in this plan.

## Verification Plan

### Review verification

- Phase 0 scope model is resolved and documented above.
- All file changes are labeled repo-local or global.
- No phase modifies global hooks (`~/.claude/hooks/`) or global commands (`~/.claude/commands/`).
- The only global file edit is `~/.claude/docs/agent-pitfalls.md` in Phase 3. This is a doc file, not a hook or command. The edit is additive (new IDs for duplicates, semantic slugs, reference table) and documented in Phase 3's blast radius note.

### Implementation verification

When work starts, verify in this order:

1. **Spike (before other Phase 2 work):** Run the update-learnings spike. Record result in `docs/reports/spike-update-learnings-noninteractive.md`. Choose implementation path (A or B).
2. **Root contract:** `head -20 /Users/alejandroguillen/Projects/sandbox/CLAUDE.md` — exists and describes autonomy classes.
3. **Non-interactive tail (behavioral):** Run a solo autopilot build on a trivial app. Capture full output. Verify: (a) "Want to run code-explainer" does NOT appear as an interactive question, (b) "Learnings Propagated" summary table DOES appear, (c) BUILD_TRACKING.md has all required sections filled.
4. **Missing artifact gate (behavioral):** Manually delete HANDOFF.md before the tail step runs. The run must fail with a specific error naming HANDOFF.md, not silently succeed.
5. **Failure registry integrity:** `grep -oP '## Failure Class \K\d+' ~/.claude/docs/agent-pitfalls.md | sort -n | uniq -d` — must return empty.
6. **Spec gate (behavioral):** Create a minimal test spec with a seeded contradiction (schema defines `user_id`, route handler references `userId`). Run the spec-consistency-checker agent. Verify output contains FAIL and names the specific field mismatch.
7. **Scope audit — sandbox repo:** `git -C ~/Projects/sandbox diff --stat` after all changes. Confirm changes are limited to expected files (CLAUDE.md, .claude/skills/, .claude/agents/, docs/reports/).
8. **Scope audit — global files (blast radius check):**
   - `md5 ~/.claude/commands/update-learnings.md` — compare before and after. Must be identical (no global command was edited).
   - `md5 ~/.claude/settings.json` — compare before and after. Must be identical (no global settings changed).
   - `ls -lt ~/.claude/hooks/` — no hook files modified after work started.
   - `diff ~/.claude/docs/agent-pitfalls.md.bak ~/.claude/docs/agent-pitfalls.md` — shows only expected changes: FC22/FC23 reassignment, semantic slugs, reference table. (Take the backup before Phase 3 work begins.)

## Open Questions (Resolved)

1. **Can sandbox override `update-learnings` locally?** No project-level command override mechanism exists. The spike determines whether the global command works as-is (Path A) or whether a sandbox-local skill replaces it for autopilot use (Path B). The global command is never edited.
2. **Should the run manifest be a separate file?** No. BUILD_TRACKING.md is sufficient. Adding a parallel JSON manifest creates dual-source-of-truth problems.
3. **Is `agent-pitfalls` better as sandbox-local?** No. It is a cross-project registry by design. Sandbox appends to it but does not own it.
4. **Which hooks should block work?** None. Hooks stay as reminders. The autopilot skill is the enforcement engine.

## Feed-Forward

- **Hardest decision:** Keeping enforcement in the autopilot skill rather than adding project-local hooks or command overrides. This is correct because the skill is the only context where blocking is appropriate — but it means all hardening logic lives in one 413-line file that is already complex. Every phase of this plan adds lines to that file.
- **Rejected alternatives:** (1) More agent autonomy without changing the control plane — rejected because the weak point is enforcement, not model capability. (2) Full global hardening first — rejected because sandbox is the right testbed and global changes increase blast radius. (3) Separate JSON manifest system — rejected because BUILD_TRACKING.md already serves this role and a parallel system creates confusion. (4) Safety profiles as a formal system — deferred because Docker-layer isolation already handles this. (5) Shifting duplicate FC IDs and renumbering subsequent classes — rejected because it invalidates historical references in solution docs.
- **Least confident:** Autopilot skill complexity after this work. The skill is already 413 lines. This plan adds: a spike result check, artifact existence gates, a BUILD_TRACKING completeness check, a uniqueness check on agent-pitfalls, and a pre-swarm consistency gate invocation. If the skill becomes too long for an LLM to follow reliably in a single context, the enforcement it provides becomes unreliable — the very problem it's meant to solve. Mitigation: measure the skill's line count after each phase. If it exceeds ~500 lines, extract verification gates into a separate helper skill that the autopilot skill calls as a single step.
