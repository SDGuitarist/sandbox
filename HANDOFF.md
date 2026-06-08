# HANDOFF — Sandbox

**Date:** 2026-06-08
**Branch:** feat/film-production-pm  (checked out; 1 commit `dd02ae0` on top of the frozen hardening branch)
**Phase:** **Spec convergence COMPLETE — ready to launch run 070.** Film Production PM is the vehicle for the orchestration-hardening **validate-on-real-build** gate. Codex round folded + human structural-verification gate **PASSED (zero P0s)**. Blocked only on launch environment (see below).

## Current State

We are converging the Film Production PM spec (16-agent swarm, run **070** target) so the next swarm both (a) ships an app and (b) field-proves the orchestration-hardening Tracks A/B/C. The spec passed an internal completeness pass; Claude Code then ran a structural verification and found 11 issues, **fixing 9** (2 P0 + 3 P1 + 1 gate-blindness + low-sev). Awaiting a **fresh-context Codex review** (handoff written, see below), then human structural verification, then launch.

Two branches, deliberately separated:
- **feat/cpaa-event-replay-simulator** `0d36a24` — orchestration-hardening, **FROZEN at Codex GO×3**. Untouched. Stays reviewable for its merge decision.
- **feat/film-production-pm** `dd02ae0` — convergence work, **inherits the hardening** so the swarm exercises it. This is the validate-on-real-build vehicle.

## Convergence — what was found & fixed

Catch ledger + dispositions: `docs/reports/film-production-pm/convergence-catches.md` (11 catches, 9 fixed).
- **F-H1/H2 (P0×2):** FTS single-writer — dropped triggers, kept explicit `index_entity`/`remove_entity` (killed double-index + impossible search-agent-owns-schema.sql conflict). Both were cross-section contradictions — the class gates can't catch.
- **F-H3 (P1):** defined the previously-undefined `VALID_PHASE_TRANSITIONS` / `VALID_SCENE_TRANSITIONS` maps.
- **F-H4 (P1):** standardized money convention (dollars in, integer cents stored).
- **F-H5 (P1):** `create_expense -> int | None` (overspend is a return value, not a 500).
- **F-G1 (P1):** added `Full Signature` column + 10 orchestration-entrypoint rows so Track B's FC50 guard **fires and passes** on the call-sheet surface.
- **F-H6 (P2):** dept_head ownership code — **OPEN, deferred to Codex round.**

**Roadmap finding (logged):** the FC50 completeness guard returns **N/A when zero orchestration-entrypoint rows are declared** — so it was silently blind to the 6-import call-sheet surface it exists to protect. Spec-template must require those rows. See `docs/roadmap-to-fully-unattended.md`.

## Key Artifacts

| Item | Location |
|------|----------|
| Spec (hardened) | docs/plans/film-production-pm-plan.md |
| Brainstorm | docs/brainstorms/2026-06-02-film-production-pm-brainstorm.md |
| Convergence catches | docs/reports/film-production-pm/convergence-catches.md |
| Codex review handoff | docs/handoffs/film-production-pm-codex-spec-review.md |
| Unattended roadmap | docs/roadmap-to-fully-unattended.md |

## Convergence: DONE (commits dd02ae0, 00049dd, 60ad283)

- Codex round (5 cross-section findings) folded.
- Human gate: 4 angle-sliced verification agents, **zero P0s**; 2 P1 + load-bearing P2s fixed (decorator-stacking-order 500, idempotent call-sheet generation, created_by pin, department_id parse guard, get_departments annotation). Full ledger: `docs/reports/film-production-pm/convergence-catches.md`.
- Watch-item (not a blocker): GET `<int:>` routes aren't in Input Validation, but RestaurantOps/GigSheet passed 9w.6 with the identical structure — if 9w.6 false-FAILs on these, that's a checker bug to log, not a spec defect.

## Next Steps (in order)

1. **LAUNCH BLOCKED ON ENVIRONMENT.** Autopilot needs `dangerouslySkipPermissions: true` in `.claude/settings.local.json` AND the session started from `~/Projects/sandbox`. This session does NOT have it. In a properly-configured session: `cd ~/Projects/sandbox`, checkout `feat/film-production-pm`, then run `/autopilot` (reads `swarm: true` from the plan → 16-agent swarm path).
2. **Confirm validate-on-real-build** in the run's reports: the **9w.6 PASS**, the **advisory spec-eval log**, AND a **per-worker cherry-pick base in `assembly-summary.md`**. A 9w.6 false-FAIL that aborts before Track A = validation INCOMPLETE (re-run, don't call it done).
3. **Then** decide the hardening branch (`feat/cpaa-event-replay-simulator`) merge — held until validate passes.

## Open Operator Decisions

- **Push** either branch to remote? (Not pushed yet — both govern the validation run.)
- **Merge** orchestration-hardening to master — **HOLD** until validate-on-real-build passes (recommendation unchanged).

## Prompt for Next Session

```
Read HANDOFF.md. This is Sandbox. We are mid spec-convergence on Film Production PM
(branch feat/film-production-pm, run 070 target) — the validate-on-real-build vehicle for
the frozen orchestration-hardening branch. Spec is hardened (9/11 catches fixed; see
docs/reports/film-production-pm/convergence-catches.md). Next: run the Codex review
(docs/handoffs/film-production-pm-codex-spec-review.md), fold findings, resolve F-H6,
do human structural verification, then launch the swarm and confirm the 3 validation proofs.
```
