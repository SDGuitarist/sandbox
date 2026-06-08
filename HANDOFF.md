# HANDOFF -- Sandbox

**Date:** 2026-06-07
**Branch:** feat/cpaa-event-replay-simulator
**Phase:** Orchestration-hardening **WORK PHASE COMPLETE** (4 commits). **NEXT: Phase 4 —
Codex binding review (manual handoff) → then validate-on-real-build.**

## ⏭️ Next Session: Phase 4 — Codex Binding Review + Validate-on-Real-Build

The orchestration-hardening plan's implementation (Phases 0–3) is **done and committed** on
`feat/cpaa-event-replay-simulator`. Four surgical commits, each a separate track:

| Commit | Track | What |
|--------|-------|------|
| `0acd660` | C | spec-eval gate (9w.8) → **advisory**; Step-10w precondition removed; RETRY/ENV_ERROR handled |
| `3185f22` | B | **FC50** orchestration-entrypoint signature-presence guard (template + CLAUDE.md + checker Check 1b + 3 fixtures) |
| `97acabe` | A | **Phase-0 spike** (16/16 + 1 + 5 PASS) — chose strategy (i) uniform cherry-pick |
| `ed38378` | A | **FC51** base-divergence-aware cherry-pick assembly + `assembly-ownership-conflict:` class + ownership base `main`→`original_branch` |

**Verification (all PASS):** spike scripts green; no hardcoded `main...` (ownership base =
`original_branch`); 0 functional readers of `spec-eval-verification`; FC50 on all 3 surfaces;
backtest fixtures FAIL/N/A/PASS as designed; solo path (≤354) untouched; `original_branch`
merge-back (swarm-runner Step 7) byte-for-byte untouched.

**Phase 4 — Codex binding review: COMPLETE (GO ×3).**
- **Round 1:** Track B **GO**, Track C **GO**, Track A **NO-GO** → **FIXED** in `1f4c5bd`.
  - Track A bug: detached-HEAD pre-flight (`git rev-parse --abbrev-ref <branch>`) was dead code —
    a branch name never resolves to `HEAD`, and the runtime contract has no worktree paths.
    Fix: removed the unfireable check; kept the merge-commit pre-flight; detached-HEAD workers
    manifest as a recorded "empty delta" no-op; first-class handling deferred (`git worktree
    list --porcelain`). Tracks B/C unchanged.
- **Round 2:** Track A **GO**. Confirmed dead check removed, merge-commit pre-flight intact,
  residual bounded to the empty-delta path, O3 invariant / uniform cherry-pick /
  `assembly-ownership-conflict:` / `original_branch` merge-back / solo path all undisturbed.
  **All three tracks clear to merge, pending validate-on-real-build.**

**Phase 4 remaining step — Validate-on-real-build:**
- The next real feature-branch swarm must exercise all three tracks in ONE run; complete ONLY
  if its reports contain the 9w.6 PASS, the advisory spec-eval log, AND a per-worker cherry-pick
  base in `assembly-summary.md`. A 9w.6 false-FAIL that aborts before Track A = validation
  incomplete, not pass.
- **Open decisions for the operator:** (a) push `feat/cpaa-event-replay-simulator`? (b) merge to
  `master` now, or hold the branch until validate-on-real-build? (c) run the compound phase
  (`/update-learnings`) — notable lessons to propagate: the detached-HEAD branch-ref dead-check,
  the strategy-(i) decision grounded in 069 evidence, and the spec-eval 0-precision demotion.

**Known cosmetic deferral:** the intro parenthetical at `SKILL.md:40` still says swarm-runner
"inlines ... merge-conflict resolution" (now inaccurate after Track A). Left as-is because it is
**above** the solo/swarm branch point (354) and editing there was out of the work-phase constraint.
Fold into Phase-4 fixes if Codex wants it corrected.

---

## Orchestration-Hardening Plan (record)

A post-Run-069 analysis produced a **converged, Codex-reviewed plan** to harden the autopilot
pipeline. It was plan→deepen→self-review→Codex-GO (×3) complete; the work phase above implemented it.

**Plan:** `docs/plans/2026-06-07-refactor-autopilot-orchestration-hardening-plan.md`
(type: refactor, manual autonomy class, `verify_first: true`). Three tracks:
- **A** (FC51): base-divergence-aware swarm assembly — one-token ownership-gate fix
  (`main`→`original_branch`) + codified per-worker cherry-pick + `assembly-ownership-conflict:` class.
- **B** (FC50): orchestration-entrypoint **signature-presence guard** in the 9w.6 completeness gate
  (NOT a call-site classifier). *(Subsumes deferred item [069-D3].)*
- **C**: demote spec-eval gate (9w.8) to advisory + remove the Step-10w precondition.

**Status:** Codex binding review returned **GO ×3, no fixes** (watch item folded). Plan passes the
4-question gate, has EARS criteria + verification commands, Feed-Forward, and a rollback note.

**Work sequence (lowest blast radius first; Track A spike-gated and last):**
1. **Phase 1 — Track C** (smallest: two `SKILL.md` edits + S4 regression-grep). Correct the 069
   narrative first (harness writes `spec-eval-verification.md` on PASS; FAIL-waive was hand-authored).
2. **Phase 2 — Track B** (template + CLAUDE.md item 1 + presence-guard check; backtest vs CPAA 069 plan = PASS, unpinned fixture = FAIL).
3. **Phase 0 — Track A spike** (MANDATORY before any Track A edit): `docs/reports/orchestration-hardening/`.
   Resolve: is `merge-base(original_branch, branch)` the true fork point across empty/multi-commit workers?
   uniform-cherry-pick (i) vs keep-merge-fork (ii)? conflict-abort routing? merge-commit/detached-HEAD pre-flight aborts?
4. **Phase 3 — Track A** implementation (`SKILL.md:647` one token + `swarm-runner.md`). Do NOT touch the
   `original_branch` merge-back.
5. **Phase 4** — Codex review (2–3 rounds) before merge, then validate on the next real feature-branch swarm.

**Critical guards:** every edit stays below the solo/swarm branch point (`SKILL.md:354`); the working
mergeable path and `original_branch` merge-back must not regress. Commit each track separately (clean
per-track rollback).

---

## Run 069 — COMPLETE (record)

CPAA Shadow Lab Event-Replay Simulator is built and fully functional. Run 069 validated the 3-stage
delegation architecture at 24 agents (2× the prior 12-agent ceiling from Run 068) with no context death
and no manual resume. Smoke 12/12 PASS, tests 30/30 PASS (1 expected skip). All 4 P1 and 2 P2 review
findings fixed. App on `feat/cpaa-event-replay-simulator`.
**Caveat (now recorded in the solution doc):** "validated at 24" ran on a 1M window — headroom is not yet
separable from window size; the 48-agent test must control for it.

### Key Artifacts
| Item | Location |
|------|----------|
| CPAA plan (FROZEN, swarm:true, 24 agents) | docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md |
| Orchestration-hardening plan (CONVERGED, this session) | docs/plans/2026-06-07-refactor-autopilot-orchestration-hardening-plan.md |
| Binding-review verdict (CPAA) | docs/reports/069/binding-review-verdict.md |
| Spec-eval waiver (CPAA) | docs/reports/069/spec-eval-waiver.md |
| Assembly summary (cherry-pick / Base-Divergence Note) | docs/reports/069/assembly-summary.md |
| Solution doc (CPAA, incl. 1M caveat) | docs/solutions/2026-06-07-cpaa-event-replay-simulator-24-agent-swarm-build.md |
| Self-audit | docs/reports/069/self-audit.md |

### Deferred Items
- **[069-D1][069-W3] GOLDEN_PROJECTION_HASH not frozen.** `compute_golden.py` has a CSRF token-reuse bug;
  `F1::test_golden_corpus_projection_hash_anchor` SKIPS gracefully. Fix: get session token from the test
  client's session (not the HTML form), run the tool, freeze the hash in `constants.py`. *(This is the one
  loose end that touches the app's core determinism proof.)*
- **[069-D2] F2 worker worktree may remain.** Manual cleanup if needed: `git worktree list` / `git worktree remove --force <path>`.
- **[069-D3] Spec §5 "Orchestration Entrypoints" row-class** — **NOW SUBSUMED by Track B** of the
  orchestration-hardening plan above.
- **[Run 068]** outcome_routes flash category (P3); list_contacts ORDER BY (P3).

### Learnings propagated (this session, post-analysis)
- agent-pitfalls: **FC50** (orchestration entrypoints), **FC51** (worktree base divergence).
- spec-eval-gate-behavior memory: 069 confirms the 2-for-2 demote case.
- Solution doc: 1M-window measurement caveat.

## Prompt for Next Session (FRESH WINDOW)

```
Read HANDOFF.md. Sandbox project, branch feat/cpaa-event-replay-simulator. Run 069 is COMPLETE.
Start the WORK phase on the CONVERGED, Codex-GO orchestration-hardening plan:
docs/plans/2026-06-07-refactor-autopilot-orchestration-hardening-plan.md (manual, refactor, 3 tracks).
Sequence: Phase 1 Track C (spec-eval demote) -> Phase 2 Track B (verb presence-guard) -> Phase 0 Track A
spike (MANDATORY, docs/reports/orchestration-hardening/) -> Phase 3 Track A. Commit each track separately.
Critical: keep every edit below SKILL.md:354 (solo/swarm branch point); do NOT touch the original_branch
merge-back; do NOT regress the working mergeable assembly path. Use /workflows:work.
```
