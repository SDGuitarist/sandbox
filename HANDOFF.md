# HANDOFF — Sandbox

**Date:** 2026-06-08
**Branch:** feat/film-production-pm  (checked out; 1 commit `dd02ae0` on top of the frozen hardening branch)
**Phase:** **Spec convergence in progress** for Film Production PM — the vehicle for the orchestration-hardening **validate-on-real-build** gate.

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

## Next Steps (in order)

1. **Codex review** — handoff at `docs/handoffs/film-production-pm-codex-spec-review.md` (already copied to clipboard once). Paste into Codex, fresh context.
2. **Fold findings** back into the spec; resolve F-H6 with Codex's proposed ownership code.
3. **Human structural verification** — cross-section field/type matching (non-optional per CLAUDE.md). Convergence criterion: Codex clean AND human finds zero P0s.
4. **Launch swarm (run 070)** from `feat/film-production-pm`.
5. **Confirm validate-on-real-build** — the run's reports MUST contain: the **9w.6 PASS**, the **advisory spec-eval log**, AND a **per-worker cherry-pick base in `assembly-summary.md`**. A 9w.6 false-FAIL that aborts before Track A = validation incomplete.
6. **Then** decide the hardening branch merge (held until validate passes).

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
