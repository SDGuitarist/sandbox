# HANDOFF — Sandbox · P1/P2 unattended multi-wave wave-barrier plan (rev 4) — awaiting Codex plan re-review

**Repo:** /Users/alejandroguillen/Projects/sandbox
**Date:** 2026-07-22
**Active branch:** feat/p1p2-unattended-swarm-wave-barrier (branched off origin/master @ 4da3eff) — pushed to origin
**Phase:** P1/P2 PLAN revision 4 — resolves the SECOND Codex plan re-review NO-GO. PLAN DOCUMENTATION ONLY; no SKILL/tool code written. **Next actor: Alex → send Codex the rev4 plan re-review handoff (below).** Do NOT begin implementation until Codex returns GO.

## Current State

Active work is the **P1/P2 trust-gate item**: encode the unattended **multi-wave swarm barrier loop** into the autopilot SKILL so a ≥20-agent swarm is launchable fully hands-off (trust criteria (2) no manual firebreak toggling + (3) wave-barrier/push mechanic from the SKILL, not live judgment). Plan: `docs/plans/2026-07-22-p1p2-unattended-swarm-wave-barrier-plan.md` (revision 3).

**rev4 resolves the SECOND Codex plan re-review NO-GO** (10 blockers). Key changes vs rev3:
- **One gate architecture (§3.4):** the firebreak stays ACTIVE for the ENTIRE run — NO deactivation, NO toggle window. The per-wave integrated dependency gate = swarm-runner contract-check (grep) **+ a new BLOCKING integrated import-smoke run as `pytest`** (firebreak-legal, identity-agnostic). NO `python -m compileall`/`<pkg>.smoke` anywhere → the H5 toggle is never exercised. This dissolves the gate-order contradiction and the "zero-live-before-deactivate" hazard (vacuous: no deactivation).
- **Spike 0a is now genuinely end-to-end:** Wave 2 authors with Wave 1 ABSENT, then BOTH waves are assembled and the INTEGRATED tree must pass a pinned `compileall` + `pytest` import-smoke. Env pinned (`.venv/bin/python` 3.14.6; no mypy → typecheck substituted by import-smoke, recorded as N/A-substituted). A dependent-wave-invalidating failure STOPS for plan revision + Codex review — NOT a silent scope cut.
- **spike_per_wave_swarm_runner moved into BLOCKING §0.0c:** fixture, commands, PASS criteria, firebreak expectations, report isolation, cleanup expectations, two-sequential-invocation no-leak proof all pinned.
- **Write-ahead resume machine (§5):** 9 durable phases; every resume re-asserts firebreak ACTIVE FIRST, then stops ALL run-scoped tasks incl. pre-persist spawns (name-prefix scan); ambiguous-assembly recovery + compare-and-reuse/conflict rules.
- **Assembly-base proof (§3.3):** ancestry repair BEFORE base is pinned; `worker_base_sha` pinned pre-spawn; per-worker head/merge-base/delta captured before cleanup; count = Σδ+1 (accounts for the `--no-ff` merge, not "count == #workers"); stale-fork fixture must FAIL.
- **verify_wave authoritative (§7):** Wave/Required/roster DERIVED from `--plan` (no caller-supplied roster); every referenced evidence file re-read + cross-checked (forged verdicts FAIL); exact run identity; full CLIs for all 3 modes; mode-sensitive HEAD checks; wave-mode cleanup DEFERRED until after verify (evidence preserved).
- **Wave schema matched to reality (§4):** swarm-planner emits `### Agent:` SECTIONS not a table, so `.claude/agents/swarm-planner.md` is ADDED to scope with a pinned per-agent `**Wave:**`/`**Required:**` format; Export-Names→file→agent normalization + duplicate/missing/unresolved/ambiguous/aggregate/out-of-roster rejection; worker rule 11 explicitly PROHIBITS cross-module execution.
- **Honest scope (§1):** now also changes `.claude/agents/swarm-planner.md`, `.claude/agents/swarm-runner.md` (wave-mode), and `.claude/skills/tail-resume/SKILL.md`.
- **Valid EARS:** `python3 tools/test_*.py --case <name>` (repo's plain-stdlib test convention); classifier baseline 282 verified → 284.
Deliverables unchanged in kind (work phase, after §0 spikes pass): `tools/wave_artifact.py`, `tools/verify_wave.py` (+tests), SKILL loop section, swarm-planner/swarm-runner/tail-resume edits, 2 file-path allowlist adds, narrowed default-branch policy.

**Parallel in-flight (this session):**
- **FC68 / 083-W6** structural fix: MERGED to `origin/master` @ 4da3eff (fast-forward, Alex-approved). Both Run-083 HIGH deferreds (083-W2, 083-W6) CLOSED. Solution: `docs/solutions/2026-07-22-fc68-firebreak-cwd-root-anchor.md`.
- **P3** (trust-gate): `tools/verify_harvest.py` + `check_compounded_darkness.py` fix on branch `feat/p3-harvest-and-darkness-tools` (pushed) — **awaiting Codex CODE review** (handoff already delivered).

**Run 083 (swarmlimit 19-agent Max-Value Wave-Barrier Swarm) is COMPLETE** (record retained below): 19 build agents / 3 waves, C2 smoke 31/31, 0 P1 / 3 P2 deferred, grade B. `origin/master` now @ 4da3eff (FC68 + P3-independent docs).

## Codex rev4 plan re-review handoff (copy-paste to Codex, fresh context)

```
You are reviewing REVISION 4 (plan only — no code written) of an autopilot plan.
Repo: /Users/alejandroguillen/Projects/sandbox
Branch: feat/p1p2-unattended-swarm-wave-barrier
Plan: docs/plans/2026-07-22-p1p2-unattended-swarm-wave-barrier-plan.md

CONTEXT. This plan encodes an unattended multi-wave swarm "wave-barrier" loop into the
autopilot SKILL so a ≥20-agent swarm can run fully hands-off. Your PRIOR (rev3) review
returned NO-GO with 10 blockers. rev4's resolution map is in the plan's "Codex re-review #2
resolution map (revision 4)" table. Your job: decide GO / NO-GO on rev4, checking each
blocker is genuinely resolved (not merely reworded).

Ground truth you should open and cross-check (do not trust the plan's claims about them):
- .claude/hooks/firebreak-classify.py — TRUSTED_PIPELINE_SCRIPT_PATHS (currently 4 paths),
  _matches_known_test_framework (pytest / python -m pytest / python -m unittest / go test /
  cargo test are identity-agnostic GREEN; python -m compileall is NOT). Classifier test
  baseline is 282/282 (verified). Confirm the plan's "firebreak stays ACTIVE, use pytest
  import-smoke, no -m carve-out" architecture is actually firebreak-legal.
- .claude/agents/swarm-runner.md — today it runs contract (grep, blocking) / smoke
  (non-blocking) / test (non-blocking), merges --no-ff to original_branch, then cleans up
  worktrees+branches (Step 8). rev4 adds a wave-mode BLOCKING pytest import-smoke, a
  Worker-Deltas record before cleanup, and DEFERS cleanup until after verify_wave. Check
  these three changes are (a) necessary, (b) side-effect-clean for single-wave (must be
  byte-for-byte unchanged), (c) sufficient to be the sole integrated dependency gate.
- .claude/agents/swarm-planner.md — today it emits repeated "### Agent: <role>" SECTIONS
  (NOT a table). rev4 §4/§7 pin a per-agent **Wave:**/**Required:** format on those sections
  and derive the verify_wave roster from it. Check the parse is unambiguous and the
  Export-Names→file→agent normalization + reject-set (duplicate/missing/unresolved/ambiguous/
  aggregate/out-of-roster + forward-ref + module-mode-gate) is total and deterministic.
- tools/check_spec_provenance.py — CLI is --default-branch/--original-branch/--spec-path/
  --repo (NO --root). Confirm §5 step 11 uses --repo correctly.
- docs/reports/083/harvest-findings.md — H5 (python -m gates deferred → Run 083 toggled the
  firebreak), H6/H9 (integrated tree did NOT boot until an assembly-fix). These justify the
  blocking import-smoke and the no-toggle architecture; confirm the reasoning holds.

SPECIFICALLY ADJUDICATE:
1. §0.0a — is it a GENUINELY falsifiable end-to-end two-wave spike (author-with-Wave-1-absent
   THEN assemble-both + integrated compile/import gate), with a STOP-for-revision (not a
   silent independent-waves scope cut) on a dependent-wave-invalidating failure? Env pinned?
2. §0.0c — is spike_per_wave_swarm_runner blocking, with fixture/commands/PASS/firebreak/
   report-isolation/cleanup/no-leak-proof all pinned?
3. §3.4 — is exactly ONE executable gate architecture pinned? Does it preserve: no unattended
   CODE push; no name/-m carve-out; only the 2 approved tool-path additions; zero live workers
   before any deactivation (here: no deactivation at all)? Is the blocking integrated
   dependency gate identified (contract grep is explicitly NOT sufficient)?
4. §5 — do the write-ahead phases cover all crash boundaries incl. partial spawn (pre-persist
   task ids), merge-before-state-write, artifact reuse-vs-conflict? Does EVERY resume re-assert
   firebreak ACTIVE first and stop ALL run-scoped tasks by name prefix?
5. §3.3 + §7 — ancestry repair before base is pinned; worker_base_sha pinned pre-spawn;
   per-worker head/merge-base/delta captured before cleanup; fork-point==pinned-base proven;
   commit count == Σ(worker deltas)+1 (the --no-ff merge), NOT "count == #workers"; stale-fork
   fixture FAILs.
6. §7 — is verify_wave authoritative: roster DERIVED from --plan (no caller-supplied roster);
   every evidence file re-read + cross-checked (forged verdict FAILs); exact run identity;
   full CLIs for --validate-schema/--wave/--reconcile; HEAD checks mode-sensitive; evidence
   preserved (deferred cleanup) until verify?
7. §4/§7 — wave schema matched to swarm-planner reality; worker prompt EXPLICITLY prohibits
   cross-module execution (rule 11), not relying on absence of a command?
8. §8 — are all EARS commands valid (python3 tools/test_*.py --case <name>; no invalid ::)?
   classifier baseline 282→284?
9. §1 — is scope honest (swarm-planner.md, swarm-runner.md, tail-resume/SKILL.md all listed)?

Return: GO or NO-GO. For NO-GO, list each unresolved blocker with the exact plan section and
what is missing. Do NOT propose code — this is a plan review.
```

## Key Artifacts

| Phase | Location |
|-------|----------|
| Spec | docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md |
| Run-plan | docs/plans/2026-07-21-feat-082-max-value-unattended-autopilot-limit-test-plan.md |
| Harvest findings | docs/reports/083/harvest-findings.md |
| Review summary | docs/reports/083/review-summary.md |
| Solution doc | docs/solutions/2026-07-22-swarmlimit-19-agent-max-value-swarm-build.md |
| Self-audit | docs/reports/083/self-audit.md (pending — being written now) |
| Disconfirmer | docs/reports/083/disconfirmer.md (pending — being written now) |
| BUILD_TRACKING | BUILD_TRACKING.md |

## Pitfall Harvest (Primary Deliverable)

| ID | root_cause_id | Failure Class | Assembly Fix? |
|----|--------------|---------------|---------------|
| H1 | RC-config-db-key-unpinned | FC5 | no (converged, not a failure) |
| H2 | RC-package-init-unowned | FC-package-init | no (benign) |
| H3 | RC-close-db-unregistered | FC3 | YES — registered teardown_appcontext(close_db) |
| H4 | RC-envelope-key-unpinned | FC30/FC5 | YES — propagated to Wave-2 briefs |
| H5 | RC-firebreak-orchestrator-gate-python | FC58 | no (toggle protocol documented) |
| H6 | RC-initdb-app-context | FC39-family | YES — with app.app_context(): init_db() |
| H7 | RC-cwd-root-drift | FC68 (net-new) | no (deferred; governance tool hardening) |
| H8 | RC-delete-envelope-divergence | FC5 | no (documented; pin in future specs) |
| H9 | RC-secretkey-env-vs-config-seam | FC69 (net-new) | YES — smoke os.environ.setdefault |

Net-new failure classes: FC68 (governance-tool cwd self-location) + FC69 (app factory config-order seam).

## Review Findings

| Severity | Count | Notes |
|----------|-------|-------|
| P1 | 0 | Feed-forward risk (process_return 4-table tx) held — no P1 |
| P2 | 3 | All deferred (throwaway vehicle): rowcount silence, TOCTOU read-then-update, DELETE envelope divergence |

## Deferred Items (carry to next session)

| Item | Severity | Notes |
|------|----------|-------|
| P2-01: restock_product_in_tx silent 0-rowcount | P2 | Protected by FK; deferred |
| P2-02: advance_shipment TOCTOU read-then-update | P2 | SQLite busy_timeout serializes; deferred |
| P2-03: DELETE-success envelope divergence (H8) | P2 | Pin all response branches in future specs |
| H5 FC58: firebreak allowlist doesn't cover python -m compileall | P2 | Toggle protocol works; extend allowlist in future |
| ~~[083-W6]~~ **CLOSED 2026-07-22** — FC68 fixed structurally on `fix/fc68-firebreak-cwd-anchor`: absolute `--root` + realpath + git-metadata main-worktree validation (fail-closed exit 3) + exit-code per-wave read-back gate. Codex NO-GO→fix→GO. | DONE | Solution: docs/solutions/2026-07-22-fc68-firebreak-cwd-root-anchor.md; 18 real-worktree tests |
| ~~[083-W2]~~ **CLOSED 2026-07-22 (same session, post-teardown)** — all 10 Path-B `--case` proofs + plain full suite run LIVE: 10/10 PASS incl. `process-return-rollback` (4-table atomic rollback via `_TX_FAULT`). Feed-forward risk now ARTIFACT-BACKED. | DONE | Evidence: docs/reports/083/case-suite-output.txt + w2-closure.md. self-audit.md NOT rewritten (point-in-time record). |
| Feed-forward seam verification: process_return passed completely | info | Spec §5 Transaction Contracts was sufficient |
| Merge decision: `fix/fc68-firebreak-cwd-anchor` → origin/master | awaits Alex | Clean fast-forward from a5cde9d. **A** = full FF (includes unrelated docs-only `c6a0d84`); **B** = FC68-only integration (excludes `c6a0d84`). FF-push to master needs explicit approval. |

## Feed-Forward Resolution

**Risk flagged:** "process_return is a 4-table atomic write reaching into 3 other agents' tables via in-tx helpers — the densest cross-agent write."
**What happened:** The feed-forward seam DID NOT FIRE. Spec §5 Transaction Contracts with Class A/B/C classification was sufficient; all 7 in-tx helpers were correctly authored as Class-C (take caller conn, never commit). The seams that fired were lifecycle/infrastructure (H3 FC3, H6 FC39, H7 FC68, H9 FC69), not business-logic.
**Delta:** Lifecycle seams are where the real integration risk lives at swarm scale, not business-logic; spec §5 transaction classification stops the commit-leakage class entirely.

## Three Questions (from solution doc Feed-Forward)

1. **Hardest decision?** Whether to classify the wave-barrier mechanic as a new pattern (yes — FC52 provenance + multi-wave origin push) or just a special case of existing FC51 worktree-base guidance. Classified as a distinct pattern because the timing of origin/master pushes between waves is the load-bearing constraint.
2. **What was rejected?** Running spec-eval harness (GUARDRAIL: Max subscription only — no raw API calls). Accepted SPEC_EVAL_SKIPPED with explicit human-approved waiver in BUILD_TRACKING.
3. **Least confident about?** Whether FC68 (governance tool cwd self-location) will reproduce on the next run or was a one-time artifact of the manual wave-barrier orchestration. Needs a live multi-wave run under SKILL.md automation to confirm.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is sandbox, on branch
feat/p1p2-unattended-swarm-wave-barrier (off origin/master @ 4da3eff).

ACTIVE: P1/P2 plan — encode the unattended multi-wave swarm barrier loop into the
autopilot SKILL. Plan doc: docs/plans/2026-07-22-p1p2-unattended-swarm-wave-barrier-plan.md
(revision 4, resolves the SECOND Codex plan re-review NO-GO — 10 blockers). PLAN ONLY — no
implementation yet.

IMMEDIATE (needs Alex): send Codex the rev4 plan re-review handoff (below in this HANDOFF).
Do NOT begin implementation until Codex returns GO. When GO:
  - Work phase starts with the §0 BLOCKING verify-first spikes: 0a (genuine end-to-end
    two-wave: author-with-prior-absent THEN assemble-both + integrated compile/import gate),
    0b (TaskStop observability), 0c (spike_per_wave_swarm_runner — two sequential invocations,
    no run-level state leak). A 0a/0c FAILURE that invalidates dependent waves = STOP for plan
    revision + Codex review; NOT a silent scope cut and NOT a work-phase judgment call.
  - Then build tools/wave_artifact.py + tools/verify_wave.py (+tests), the SKILL loop
    section, the swarm-planner/swarm-runner/tail-resume edits, 2 file-path allowlist adds,
    and the narrowed default-branch policy.

DESIGN X (load-bearing): unattended runs push NO code to origin/<default>; workers
write+commit only (rule 11 prohibits cross-module execution); integration + all
self-verification deferred to per-wave assembly on the local feature branch. The spec (not
code) reaches worktrees via the ONE-TIME pre-Wave-0 provenance repair. GATE ARCHITECTURE
(rev4): firebreak stays ACTIVE all run — no toggle; the blocking integrated gate is
swarm-runner contract-check + a pytest import-smoke. Firm constraint: no unattended CODE
push to master.

PARALLEL in-flight:
- FC68/083-W6: MERGED to origin/master @ 4da3eff (Alex-approved FF).
- P3 (feat/p3-harvest-and-darkness-tools, pushed): verify_harvest.py + darkness fix —
  awaiting Codex CODE review.
- P4 (≥20-agent unattended baseline run): BLOCKED on P1/P2 + P3 merged. Do NOT launch.
- FC59 master declutter: needs Alex sign-off.

INVARIANTS: firebreak deny-known-bad; TRUSTED_PIPELINE_SCRIPT_PATHS file-only, no -m carve-out;
Gate-8 fail-closed; builds namespace under own top-level dir (FC59); self-audit-reviewer stays
Sonnet; disconfirmer stays Opus; NEVER pay usage credits — Max subscription only.
Do NOT push to origin/master without Alex's explicit approval.
```

---

<details><summary>Prior — Run 082 (swarmlimit spec convergence): COMPLETE, CONVERGED — spec status: active</summary>

**Branch:** feat/082-swarmlimit-spec (same branch — Run 083 is built ON this branch)
**Spec:** docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md (status: active, converged 4 Codex rounds + human pass)
Four Codex passes + human structural verification: Codex-clean AND human-zero-P0. Spec flipped draft→active. Run 083 launched from this converged spec.

</details>

<details><summary>Prior — Run 081 (Lesson Studio 30-agent scale-validation): COMPLETE, PIPELINE_PASS_WITH_DEFERRED_RISK</summary>

Run 081 COMPLETE (2026-07-10). 30-agent swarm, largest governed run. G1 probe PASS ×3, FC58 trusted scripts green, telemetry 4/4, FC62 found+fixed post-teardown (invoice.items Jinja dict-method shadowing → 500; dynamic surface only catch). Smoke 23/23 PASS. Grade B. Master @ 8d786b8 pushed.

</details>
