# HANDOFF — Sandbox · master @ P1/P2 wave-barrier verifier + P3 FC-harvest gate MERGED (both Codex GO)

**Repo:** /Users/alejandroguillen/Projects/sandbox
**Date:** 2026-07-23
**Active branch:** master — **both feature branches are now merged here.** `feat/p1p2-unattended-swarm-wave-barrier` (`fe07332`) fast-forwarded master; `feat/p3-harvest-and-darkness-tools` (`9ca21c1`) merged on top via `--no-ff` (this commit). Merge base for both was `4da3eff` (FC68). This reconciles the previously-fragmented HANDOFF (todo 075 — now resolved).
**Phase:** BOTH review gates are **Codex CODE-review GO** and merged:
  - **P1/P2 §1** (authoritative multi-wave wave verifier, `tools/verify_wave.py`): NO-GO (2 gaps) → fixed → re-review **GO**. Result: `docs/reports/p1p2-spikes/codex-1-rereview-result.md`. Suites: verify_wave 40/40, wave_artifact 15/15.
  - **P3** (FC-harvest value gate `tools/verify_harvest.py` + compounded-darkness fix): NO-GO (3 findings) → fixed → re-review **GO**. Result: `docs/reports/p3/codex-rereview-result.md`. Suites: verify_harvest 17/17, compounded_darkness 13/13.
  - Merged firebreak classifier suite: **285/285** (282 base + 2 wave tools + 1 verify_harvest); TRUSTED_PIPELINE_SCRIPT_PATHS now pins all of verify_wave/wave_artifact/verify_harvest/check_compounded_darkness/check_spec_provenance/verify_delegated_status/firebreak-activate.
Do NOT launch any autopilot run — **P4 (≥20-agent unattended baseline) stays gated** on the trust gate + explicit human go. P1/P2 + P3 (its tooling prerequisites) are now MERGED; the remaining gate items are a live run's criteria, not more tooling.

## §1 CODE-review NO-GO — FIXED (2 gaps closed in tools/verify_wave.py)

Both were under-implemented plan §7 rejects; both now enforced in BOTH `--wave K` and `--reconcile` (fix commits `c7c4da5` tool + `c0c1adf` tests). Full write-up: `docs/reports/p1p2-spikes/codex-1-fix-result.md`.
1. **Authoritative status/count** — `verify_wave()` now FAILs unless `status == PASS-EMITTED` (a forged `ABORT` artifact no longer passes `--wave K`) AND `int(wave_count)` equals the plan's declared `waves` (threaded in via a `declared_waves` param; `cmd_wave` parses it, `cmd_reconcile` passes `N`).
2. **prev_wave_artifact_sha tamper-evidence** — for `k>1`, `verify_wave()` recomputes `sha256(w<k-1>/wave.md)` and FAILs on mismatch/missing. `--wave K` derives the sibling `w<K-1>/` of `--reports-dir`; `--reconcile` now USES the previously-dead `prev_artifact_path`. New `sha256_file()` mirrors `wave_artifact.py._sha256_file` (share-not-import).

**Verify:** `python3 tools/test_verify_wave.py | tail -1` → `36/36`; classifier `284/284`; wave_artifact `15/15`. Diff `2773000..HEAD` touches ONLY the two tools files; single-wave paths + firebreak logic untouched; no new caller-trusting input. Residual risks in `codex-1-fix-result.md` (declared_waves=None permissive branch; forged-sha fixture appends after the fence; multi-wave `--reconcile` cases still live-spike-covered).

## §1 Implementation (Session 1) — DONE (5 checkpoints, all pushed)

All wave-mode logic gates on `waves > 1` / `wave_index`; **single-wave behavior is byte-for-byte unchanged**. Firebreak classifier LOGIC untouched (data-only allowlist adds); worker base ref unchanged; only the two approved tool-path allowlist adds.

| # | Deliverable | Evidence |
|---|-------------|----------|
| 1 | `.claude/hooks/firebreak-classify.py` — add `tools/wave_artifact.py` + `tools/verify_wave.py` to `TRUSTED_PIPELINE_SCRIPT_PATHS` (TRUSTED-only, PATH-pinned, worker-denied; NO logic/`-m` change) | classifier suite **282→284** |
| 2 | `tools/wave_artifact.py` (+ `test_wave_artifact.py`) — `emit` (atomic wave.md, §6 schema, prev-artifact sha) + `state` (atomic transition-state) | **15/15**, `--case` selector |
| 3 | `tools/verify_wave.py` (+ `test_verify_wave.py`) — `--validate-schema` (§4) / `--wave K` (§7) / `--reconcile` (§7); truth derived from `--plan`+`--spec-path`+live git+re-read evidence | **32/32**, `--case` selector |
| 4 | `.claude/skills/autopilot/SKILL.md` — "Multi-Wave Barrier Loop (Path B)" section (§5 sequence + write-ahead state + resume pointer; firebreak ACTIVE all run, no toggle) | committed |
| 5 | `.claude/agents/swarm-planner.md` (Wave/Required emit), `.claude/agents/swarm-runner.md` (Step 4.5 blocking import-smoke + Worker-Deltas + deferred cleanup), `.claude/skills/tail-resume/SKILL.md` (Step 0 Wave-Resume + Step 2b `--reconcile` fail-closed), `CLAUDE.md` (§3.5 push policy) | committed |

**Verify:** `python3 .claude/hooks/test_firebreak_classify.py | tail -1` → `284/284`; `python3 tools/test_wave_artifact.py` → `15/15`; `python3 tools/test_verify_wave.py` → `32/32`.

### §1 remaining risks / honest gaps (for the CODE review to scrutinize)
- **verify_wave `--reconcile` unit coverage is light** (1 degenerate 1-wave reconcile test). The multi-wave chain/ancestor reject cases (`test_reconcile_chain_break`, `_earlier_wave_ancestor`, `_final_wave_is_head`, `_count_mismatch` from §8) are NOT yet unit-tested — they are exercised by the live multi-wave run (plan §8's live-spike posture). `--wave K` is covered by 17 git-fixture cases incl. forged-verdict, required-worker, HEAD-mismatch, firebreak-inactive, post-terminal containment.
- **The §4 schema parser pins concrete spec formats** it reads: the Cross-Boundary Wiring Table (`Symbol | Producer File | Consumer File | Build-Order-Sensitive | Import Path`), Coordinated Behaviors `**Members of <token>:** a, b`, and Export Names `Defined By` (for out-of-roster). Real wave-mode specs MUST emit these; documented in swarm-planner.md. `out-of-roster` is a distinct check via Export Names `Defined By`; file-level unmapped refs surface as `missing`/`unresolved`.
- **`ambiguous`** is implemented as "same symbol produced by two different agents" (duplicate-file is caught earlier as `duplicate`).
- **No live governed run yet** — the loop is encoded but unproven end-to-end; the tools were unit-tested against temp repos + an activated firebreak sentinel, not a real autopilot session. This is P4's job and stays gated.
- **SKILL Path B is orchestration prose**, not executable code — the CODE review should check the encoded step order matches plan §5 and that single-wave paths are untouched.

## Codex §0 spike-review resolution (rev5 — this session)

Codex returned NO-GO on the §0 verify-first spike review with 4 findings; all resolved:
1. **0a strengthened** (not narrowed) — the integrated gate now BOOTS `create_app()` and catches the app-context/teardown lifecycle class (H3/H6/H9): a minimal-Flask fixture whose broken assembly FAILS with the genuine `RuntimeError: Working outside of application context`, then the assembly-fix PASSES. §0.0a/§3.4 claims narrowed to exactly what 0a proves. Re-run: **PASS** (`docs/reports/p1p2-spikes/0a-result.md`).
2. **§3.1 orphaned-detached-child policy** — OUT of scope for prove-zero-live (declared F6 residual) + a `terminal_head_sha` post-terminal-commit containment check wired through §5/§6 and the §7 `verify_wave` reject-set.
3. **"typecheck" purged** — the gate is an integrated import-smoke + create_app() boot, NOT static type checking (no checker configured); surviving tokens are only prohibition/rejection lists.
4. **0c reshaped + RUN** — real `origin/<default>`-vs-`original_branch` ancestry (spike-default behind + local bare `spikeorigin` ref; spike-feat ahead; workers rooted on default tip). swarm-runner spawned ×2 (fresh context), both PASS; adjudicator's 10 checks all PASS incl. every cherry-pick base == spike-default tip. **PASS** (`docs/reports/p1p2-spikes/0c-result.md`).

Fresh Codex §0 re-review handoff: **`docs/reports/p1p2-spikes/codex-0-rereview-handoff.md`** (leads with repo/branch/HEAD/ask). §0 rollup: `docs/reports/p1p2-spikes/0-summary.md` (STATUS: COMPLETE).

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
Read HANDOFF.md for context. This is sandbox, on master @ cc3dc11.

STATE: P1/P2 (multi-wave wave-barrier verifier) + P3 (FC-harvest gate + darkness fix) are
BOTH Codex CODE-review GO and MERGED to master. The unattended multi-wave barrier loop is
fully encoded in the autopilot SKILL + agents + tools (verify_wave 40/40, verify_harvest
17/17, classifier 285/285). What has NOT happened: the loop has never run end-to-end fully
unattended (Run 083 hand-ran the barriers).

YOUR FIRST TASK: run the P4 DRESS REHEARSAL. Read the full launch brief at
docs/plans/2026-07-23-p4-dress-rehearsal-launch-brief.md and execute it — a scaled-down
(waves:2, ~6-8 agents) throwaway autopilot-swarm build ("PlantPal") whose ONLY goal is to
prove the SKILL wave-barrier loop runs hands-off with 0 interventions, BEFORE the full
≥20-agent P4 baseline. The brief has the pre-launch checklist (BLOCKING), the exact
/autopilot command, the 0-intervention success criteria, and the go-wrong / after steps.
Do the §3 pre-launch checklist FIRST; if any BLOCKING item fails, STOP and report — do not
launch. Do NOT jump straight to the ≥20-agent P4; that is the NEXT run only if this passes.

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
