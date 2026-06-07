# HANDOFF -- Sandbox

**Date:** 2026-06-07
**Branch:** feat/cpaa-event-replay-simulator
**Phase:** CPAA simulator — Stage 1 COMPLETE (plan CONVERGED + binding-reviewed + human-verified).
**LAUNCH-READY. Stage 2 (unattended swarm build) must be launched FROM A FRESH CONTEXT WINDOW.**

## Current State

CPAA Shadow Lab Event-Replay Simulator is the next autopilot BUILD target (24-agent swarm — the test of
whether the 3-stage delegation architecture survives ~2× the validated 12-agent ceiling, Run 068).

**Stage 1 is DONE and the spec is FROZEN + committed.** It went:
brief → `/deepen-plan` (11 agents) → Codex convergence (7 rounds) → human `grill-me` pass →
final MANUAL Codex binding review (2 rounds, both GO) → P1/P2 fixes committed.

**Convergence criterion MET** (Codex clean AND human zero-P0):
- Stage-1 human gate caught the one real P0 automated Codex missed — §4.4 event taxonomy diverged from the
  real corpus in 6 of 9 event types. Reconciled (commit 8833f80); generator fork stays minimal.
- Binding review (round 1) returned **GO** with one P1 + one P2; both FIXED (commit 9228983):
  - **P1:** `reset_done` now has a single named writer — `mark_complete_pass` (stated in §5/§9/§3.2 C).
    T2 always resets before it, so every COMPLETE_PASS carries `reset_done=1`, no new param/branch.
  - **P2:** §3.2 B′ now states the 15-min reaper's runtime budget explicitly (replay is sub-second;
    ~1000× margin; single-writer/single-host/synchronous, no heartbeat needed).
- Binding review (round 2, delta re-confirm) returned **GO** — both findings closed, no new contradiction.
- Full verdict + audit trail: `docs/reports/069/binding-review-verdict.md`.

**The unattended swarm BUILD has NOT started.** Do NOT launch it from the session that finished Stage 1
(context already partly consumed — would eat the inline-spawn headroom and dirty the `context_proxy_chars`
baseline). Launch from a fresh window.

## Pre-Launch Prerequisites — ALL ✅ (verified 2026-06-07)

- ✅ `.claude/settings.local.json` → `dangerouslySkipPermissions: true`.
- ✅ `BUILD_TRACKING.md` seeded for **Run 069** (24 agents, branch, `final_status: NOT_STARTED`,
  `context_proxy_chars: 0`). Run 068 tracking archived → `docs/reports/068/BUILD_TRACKING-final.md`.
- ✅ Agent-pitfalls injection — autopilot **Step 1.6** injects `~/.claude/docs/agent-pitfalls.md` into
  every worker brief; plan §16 also bakes applied pitfalls in.
- ✅ Worktree strategy — autopilot **Step 10w** spawns each of the 24 workers in its own isolated worktree
  (branch `worktree-agent-<agentId>`, disjoint file ownership → zero merge conflicts by design);
  **Step 10.5w** ownership gate validates each branch's diff; **swarm-runner** does assembly/merge/cleanup
  in fresh context. Orchestrator runs on `feat/cpaa-event-replay-simulator`; no stale worktrees.
- ✅ run-id math: 68 solution docs + 1 = **069** (matches tracking; `docs/reports/069/` exists).

## Key Artifacts

| Item | Location |
|------|----------|
| Plan + shared spec (CONVERGED, swarm:true, 24 agents, status:ready) | docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md |
| Binding-review verdict (PASS, both rounds GO) | docs/reports/069/binding-review-verdict.md |
| Binding-review handoff prompt (manual Codex) | docs/reports/069/codex-binding-review-handoff.md |
| BUILD_TRACKING (seeded for 069) | BUILD_TRACKING.md |
| Brief | docs/briefs/2026-06-06-cpaa-event-replay-simulator-brief.md |
| Corpus (reuse) | cpaa-shadow-lab/instance/shadow_lab.db (1,595 events), cpaa-shadow-lab/generate_scenario.py |

Branch commits: deepened plan (640e48a), converged (e08c030), corpus reconciliation (8833f80),
BUILD_TRACKING reseed (97b7afa), binding-review P1/P2 fixes (9228983), launch-ready handoff (this commit).

## Next Session (FRESH WINDOW): Launch Stage 2 — after explicit human GO

This is a **Stage-2 entry**, NOT a from-scratch autopilot run. The autopilot skill is written for the full
loop (Steps 1–6 = compound-start → brief → brainstorm → refinement → plan → deepen). Those are ALL DONE.
The launch command below **overrides** the skill to skip them and build against the frozen plan.

⚠️ **The single critical risk:** if autopilot heads into PLANNING instead of gates+spawn, it will overwrite
the converged spec. The orchestrator MUST enter at Step 5.5 and build against the existing plan path. If it
shows any sign of re-planning, STOP immediately.

**Launch command (run only after explicit human GO + confirmed zero-P0):**

```
/autopilot Stage 2 (unattended) build against the already-CONVERGED, human-verified, binding-reviewed plan:
docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md  (swarm:true, 24 agents, Run 069).

Stage 1 (brainstorm → plan → deepen → Codex convergence → human verification → binding review) is COMPLETE
and FROZEN (see docs/reports/069/binding-review-verdict.md). DO NOT re-run Steps 1–6 (compound-start, brief,
brainstorm, brainstorm-refinement, plan, deepen) and DO NOT overwrite the plan. Enter at Step 5.5 (run_id
computes to 069; docs/reports/069/ and BUILD_TRACKING.md are already seeded for Run 069). Then run the
pre-swarm gates in order — 9w.5 spec-consistency, 9w.6 spec-completeness, 9w.7 gate-verification, 9w.8
spec-eval — against the frozen spec, then spawn the 24 workers in worktrees per Step 10w. Inject
agent-pitfalls (Step 1.6). Branch: feat/cpaa-event-replay-simulator. All spawned agents use
mode: bypassPermissions.
```

**During the run — meta-goal instrumentation:** watch `context_proxy_chars` at each phase boundary. The
inline phases (spawn + ownership gate, Steps 7w–10.5w) can't be delegated and are the unproven part at 24
agents. **>~70% before Step 17w = a finding** → triggers the Orchestration Hardening plan (don't just push
through; record it).

## Deferred / Carried Forward

- **Plan A** (orchestration hardening) COMPLETE + merged (PR #10); solution doc on master (f90aed8).
  Plan B (spec-eval gate demotion + 7th read-path completeness surface) still un-started — separate track.
- **[068-W1]** outcome_routes flash category (P3); **[068-W2]** list_contacts ORDER BY (P3).
- Optional pre-launch: run the spec through NotebookLM for the external-data cross-ref step (already
  reconciled once; the §4.4 corpus P0 was caught and fixed).

## Prompt for Next Session (FRESH WINDOW)

```
Read HANDOFF.md. Sandbox project, branch feat/cpaa-event-replay-simulator. The CPAA event-replay
simulator is LAUNCH-READY: Stage-1 plan CONVERGED + binding-reviewed (Codex GO ×2) + human zero-P0,
all prereqs ✅, changes committed. This is a STAGE-2 launch (build against the frozen plan — do NOT
re-plan or overwrite it). Confirm prereqs are still green, then present the exact Stage-2 launch
command from HANDOFF.md and WAIT for explicit human GO. On GO, launch autopilot-swarm with the
skip-Steps-1–6 override, watch context_proxy_chars, and STOP if it heads into planning.
```
