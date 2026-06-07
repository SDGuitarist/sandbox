# HANDOFF -- Sandbox

**Date:** 2026-06-06
**Branch:** feat/cpaa-event-replay-simulator (pushed to origin)
**Phase:** CPAA simulator — Stage 1 (plan) CONVERGED + human-verified. Pre-launch prereq check PENDING.

## Current State

CPAA Shadow Lab Event-Replay Simulator is the next autopilot BUILD target (24-agent swarm — the test of
whether the 3-stage delegation architecture survives ~2x the validated 12-agent ceiling, Run 068).

The Stage-1 spec is launch-ready pending the prerequisite check below. It went:
brief → `/deepen-plan` (11 agents) → Codex convergence (7 `codex exec` rounds) → human `grill-me` pass.

**The human gate caught a real P0 that automated Codex missed:** §4.4's event taxonomy was authored from
event *counts* and diverged from the real corpus (`cpaa-shadow-lab/generate_scenario.py`) in 6 of 9
event types, including a structurally broken financial model. Reconciled: `station_state` gains
`sales_total_cents` (POS transactions); `auction_state(lot_id)` for bids; flat weather columns;
alerts keyed `alert_type:source`. The generator fork is now minimal (no payload remapping — the corpus
stays authentic). Codex re-verified the reconciliation: CONVERGED.

This is a **manual** Stage 1; the unattended swarm BUILD has not started.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brief (READY-TO-LAUNCH) | docs/briefs/2026-06-06-cpaa-event-replay-simulator-brief.md |
| Plan + shared spec (CONVERGED, swarm:true, 24 agents) | docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md |
| Spec-consistency report | docs/reports/069/spec-consistency-check.md |
| Corpus (reuse) | cpaa-shadow-lab/instance/shadow_lab.db (1,595 events), cpaa-shadow-lab/generate_scenario.py, config.py |

Commits on branch: brief hardening, deepened plan (640e48a), converged (e08c030), corpus reconciliation (8833f80).

## Next Session: Pre-Launch Prerequisite Check (then GO/launch)

1. **Launch prerequisites (verify/seed):**
   - `.claude/settings.local.json` has `dangerouslySkipPermissions: true`.
   - `BUILD_TRACKING.md` seeded from `~/.claude/docs/autopilot-tracking-template.md` at run root.
   - Autopilot skill injects agent-pitfalls into worker briefs (per ~/.claude/CLAUDE.md).
   - Confirm worktree strategy for the swarm.
2. **Binding review = MANUAL Codex** (human-driven handoff prompt), NOT headless `codex exec` — Alex's
   call: headless may use a weaker model AND it isn't truly independent since Claude orchestrates it.
   See memory `feedback_codex_manual_review`.
3. **Optional:** run the spec through NotebookLM for the external-data cross-ref step of the convergence loop.
4. **Then explicit human GO** → launch autopilot-swarm against the plan.

## Deferred / Carried Forward

- **Plan A** (orchestration hardening) COMPLETE + merged (PR #10); solution doc now on master (f90aed8).
  Plan B (spec-eval gate demotion + 7th read-path completeness surface) still un-started — separate track.
- **[068-W1]** outcome_routes flash category (P3); **[068-W2]** list_contacts ORDER BY (P3).
- Meta-goal bet (accepted): inline deepening + worker spawn surviving 24 agents; instrument
  `context_proxy_chars`; >~70% before Step 17w = finding → triggers Orchestration Hardening plan.

## Prompt for Next Session

```
Read HANDOFF.md. This is the sandbox project, branch feat/cpaa-event-replay-simulator.
The CPAA event-replay simulator Stage-1 plan is CONVERGED + human-verified
(docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md, swarm:true, 24 agents).
Run the pre-launch prerequisite check: settings.local.json dangerouslySkipPermissions,
seed BUILD_TRACKING.md, confirm pitfalls injection + worktree strategy. Do NOT launch.
Then prep the autopilot launch command and a MANUAL Codex handoff prompt for the final
binding review (not headless codex exec). Stop for explicit human GO before launching.
```
