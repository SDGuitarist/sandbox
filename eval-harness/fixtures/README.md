# Orchestration-Hardening Fixture Suite

Negative-test fixtures that prove each shipped orchestration-hardening guard
**fires** on an engineered trigger — a deterministic regression net re-run on
every future hardening edit. Driven by `../validate_hardening.py`.

Source plan: `docs/plans/2026-06-08-feat-hardening-fixture-suite-plan.md`.
Source proposal: `docs/proposals/validate-hardening-on-fixtures.md`.

## Why this exists

Run 070 spent ~2.5M tokens validating Tracks A/B/C on a real app and **never
exercised Track B** (Film PM's cross-boundary calls were all model-layer, already
pinned, so the FC50 failure mode could not occur). Track B is the only track still
unproven and it gates a confident merge of the hardening to master. F-B1 turns
Track B from "present but unexercised" into "fixture-proven" for a fraction of the
cost, and breaks the self-validation circularity.

## Fidelity label vocabulary (the honesty contract, M6)

A fixture's matrix row carries TWO axes. The fidelity axis must report the label
the invocation actually earned — never rounding up:

| Label | Meaning |
|-------|---------|
| `EXERCISED` | Drove the shipped artifact itself (e.g. invoked the real agent). |
| `SPIKE-VALIDATED` | Ran an existing spike *copy* of the recipe, not the ship. |
| `PROSE-ASSERTED` | Checked an orchestrator-prose contract; no executable guard. |
| `MIRRORED` | Ran a Python *reimplementation* — a last resort, never `EXERCISED`. |

Second axis: `PASSED` (the guard produced the expected verdict) | `FAILED`.

## Phase status

- **Phase 1 (this commit): F-B1 — Track B / FC50.** EXERCISED via the real
  `spec-completeness-checker` agent. The decisive, merge-blocking evidence; does
  not depend on the Phase-2 path choice.
- **Phase 2 (F-A1, F-A2, F-D1) and Phase 3 (F-B2, F-C1): not built.** Phase 2 is
  gated on the operator's P-extract / P-promote / P-accept choice for Track A +
  FC52-detection (see the plan's Deepening findings).
