---
title: "P1/P2 — Encode the unattended multi-wave swarm barrier loop"
date: 2026-07-22
status: draft
phase: plan
branch: feat/p1p2-unattended-swarm-wave-barrier   # to be created at work phase
relates_to:
  - unattended-big-run-trust-gate (MEMORY)
  - swarmlimit-run-083 (harvest H5/H7)
  - fc68-firebreak-cwd-root-anchor (merged 4da3eff)
feed_forward:
  risk: "A SKILL-encoded wave loop still relies on the orchestrator FOLLOWING it under context saturation — the same failure family (dropped bookkeeping) that motivated disk-verify. If the loop is prose the orchestrator can skip, it isn't really 'encoded'."
  verify_first: true
---

# P1/P2 — Encode the unattended multi-wave swarm barrier loop

## Context

The trust gate (`unattended-big-run-trust-gate`) blocks launching a ≥20-agent swarm
fully hands-off. Run 083 succeeded only because a human hand-ran the wave barriers,
approved every master push, and cat-verified the firebreak after a live fail-open.
Three of the five trust criteria are the target here:

- **(2) firebreak needs no *manual* toggling** — the H5/FC58 gap: the orchestrator's own
  `python -m compileall` / `python -m <pkg>.smoke` per-wave gates are deferred by the
  firebreak (`-m` mode has no path-pinnable script — deliberate, SKILL 803-814). Today a
  human toggles the firebreak around them.
- **(3) the wave-barrier / master-push mechanic runs from the SKILL, not live judgment** —
  Step 10w spawns all workers ONCE; there is no multi-wave loop. Run 083's 3 waves were
  orchestrator judgment.
- Residual FC68/H7 cwd-drift safety at **wave transitions** (the merged FC68 fix anchored
  `firebreak-activate.py`; the SKILL wave steps must reuse the captured `<MAIN>`, never
  re-derive from a possibly-drifted cwd).

P1 (FC68/083-W6) is already merged (`4da3eff`). What remains of P1 is the **H5 toggle**,
which is already *documented* (SKILL 803-814) but not *integrated into a deterministic
loop*. So P1 and P2 collapse into ONE deliverable: encode the multi-wave barrier loop.

## 1. What exactly is changing?

All changes are in **documentation / orchestration instructions**, not runtime security code.

1. **SKILL.md — new "Multi-Wave Barrier Loop (Path B)" section** wrapping Step 10w. Given
   plan frontmatter `waves: N` (+ a per-wave agent grouping in the assignment table), the
   orchestrator MUST, for each wave in order:
   a. Re-run the **1b firebreak read-back gate** with `--root <MAIN>` (confirm ACTIVE) before spawning the wave.
   b. Spawn that wave's workers (existing Step 10w spawn logic, scoped to the wave's rows).
   c. Barrier: wait for ALL of the wave's workers to reach a terminal on-disk status.
   d. Run that wave's assembly/parse/smoke gates bounded by the **existing** toggle protocol
      (SKILL 803-814): `deactivate --root <MAIN>` → gate(s) → `activate <run-id> --root <MAIN>`
      → read-back. No firebreak code change.
   e. Only after read-back confirms ACTIVE, proceed to the next wave.
   After the final wave, proceed to Step 11w-16w assembly / Step 17w tail as today.
2. **SKILL.md — "FC68 `<MAIN>` reuse contract"**: every firebreak op and repo-root-relative
   gate inside the wave loop uses the `<MAIN>` captured once at Step 9w.9.6; the SKILL
   explicitly forbids re-deriving the root from cwd inside the loop.
3. **CLAUDE.md + SKILL.md — Master-Push Policy (decision A)**: an unattended autopilot run
   NEVER pushes to `master`/`origin/master`. The orchestrator/tail merges only to the
   feature branch; the master merge is always deferred to a human (recorded as a HANDOFF
   deferred item). This codifies the invariant already exercised for FC68.
4. **`waves: N` frontmatter contract**: document the plan-frontmatter field + the per-wave
   grouping the assignment table must carry, and a validation step that FAILs if `waves > 1`
   but the assignment table has no wave grouping.

## 2. What must NOT change?

- **The firebreak carve-out.** No new `-m` / name-based module carve-out in
  `firebreak-classify.py` (SKILL 803-814 explicitly forbids it; `sys.path` module
  resolution is weaker than path-pinning). `TRUSTED_PIPELINE_SCRIPT_PATHS` stays file-only.
  Firebreak classify tests must remain **283/283** with no new `-m` allow-case.
- **Single-wave runs.** A plan with no `waves:` (or `waves: 1`) must behave EXACTLY as today
  — the loop degenerates to the current single Step 10w spawn, no between-waves gate window.
- **Worker governance.** The firebreak is never off across a worker spawn; the toggle window
  is a barrier with zero workers live (unchanged invariant).
- **The pre-spawn provenance gate (9w.9.5).** It runs before any worktree exists (cwd is
  main root); it is out of scope and must not be "hardened" with a non-existent `--root`
  flag (`check_spec_provenance.py` takes `--repo`, default `.`).

## 3. How will we know it worked? (Acceptance Tests — EARS)

### Happy path
- WHEN a plan declares `waves: 3` with a wave-grouped assignment table THE SYSTEM SHALL
  (the SKILL SHALL instruct the orchestrator to) spawn workers in 3 ordered waves, each
  preceded by a firebreak read-back and followed by a toggle-bounded gate window before the
  next spawn.
  - Verify: `grep -n "Multi-Wave Barrier Loop" .claude/skills/autopilot/SKILL.md` returns the
    new section; the section contains the ordered sub-steps a–e including `--root <MAIN>`.
- WHEN a plan has no `waves:` field (or `waves: 1`) THE SYSTEM SHALL behave identically to the
  current single-wave Step 10w (no between-waves gate window).
  - Verify: the loop section states the `waves ≤ 1` degenerate case explicitly.
- WHEN an unattended run completes all gates THE SYSTEM SHALL NOT push to master; it merges to
  the feature branch and records the master merge as a HANDOFF deferred item.
  - Verify: `grep -ni "never push.*master\|defer.*master" CLAUDE.md .claude/skills/autopilot/SKILL.md`
    returns the policy; `grep -n "push origin .*:master\|push .*master" .claude/skills/autopilot/SKILL.md`
    returns NOTHING in the autopilot path.

### Error cases
- WHEN a between-waves gate FAILS THE SYSTEM SHALL abort the run (reactivate firebreak +
  read-back first) and NOT spawn the next wave.
  - Verify: the loop section prescribes reactivate→read-back→abort on gate failure.
- WHEN `waves > 1` but the assignment table carries no per-wave grouping THE SYSTEM SHALL FAIL
  the pre-spawn validation with a clear message (no silent single-wave fallback).
  - Verify: the validation step is present and named in the loop section.
- WHEN the firebreak read-back after reactivation does NOT report ACTIVE THE SYSTEM SHALL abort
  before spawning the next wave (never spawn ungoverned — the H7 failure).
  - Verify: sub-step (e) requires an ACTIVE read-back as the gate to proceed.

### Regression
- WHEN the firebreak classifier test suite runs THE SYSTEM SHALL report 283/283 with no new
  `-m` allow-case.
  - Verify: `python3 .claude/hooks/test_firebreak_classify.py | tail -1` → `283/283 passed`.

## 4. Most likely way this plan is wrong

The Feed-Forward risk: **"encoded in the SKILL" ≠ "the saturated orchestrator will follow it."**
Run 050/083 showed a context-saturated orchestrator drops bookkeeping. A prose loop can be
skipped just like a manual barrier. Mitigations to decide at work phase:
- Make each wave transition leave a **disk artifact** (e.g. `docs/reports/<run-id>/wave-<k>.md`
  with the read-back result) so a downstream deterministic gate can verify the loop actually
  ran N times — turning "did the orchestrator loop?" into a disk-verifiable fact, not trust.
- A `waves: N` vs. `wave-<k>.md` count reconciliation in the tail (fail-closed if fewer wave
  artifacts than declared waves) would give the loop real teeth. **This may be the actual P2
  deliverable rather than the prose loop itself** — flag for Codex plan review.

## Feed-Forward
- **Hardest decision:** Whether to widen the firebreak carve-out for `-m` gates (rejected) vs
  encode the toggle loop (chosen). The existing SKILL 803-814 already forbids the carve-out, so
  the decision was really "honor the existing intent and make it deterministic," not re-litigate.
- **Rejected alternatives:** (a) firebreak `-m` module allowlist — widens the security surface,
  explicitly forbidden by 803-814. (b) auto-push master when gates are green — surrenders the
  human master-gate the owner has exercised twice; rejected for master-push policy A.
- **Least confident:** That a prose-encoded loop is enough. The mitigation (disk-verifiable
  per-wave artifacts + a tail reconciliation gate) may need to BE the deliverable. This is the
  item Codex plan review should scrutinize hardest.
