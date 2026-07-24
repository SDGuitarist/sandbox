# HANDOFF — Sandbox · feat/p3-harvest-and-darkness-tools

> **P3 status (this branch), 2026-07-23:** the FC-harvest value gate + compounded-darkness fix
> are **Codex CODE-review GO** (round-2, tip `99e27f3`). Result: `docs/reports/p3/codex-rereview-result.md`
> (fixes in `codex-fix-result.md`). Suites: verify_harvest 17/17, compounded_darkness 13/13,
> classifier 283/283. NOT merged to master (Alex's call per §3.5); P4 stays gated.
> The body below is the **pre-P3 FC68-era snapshot** — the authoritative current project HANDOFF
> lives on `feat/p1p2-unattended-swarm-wave-barrier`; these are reconciled at master-merge
> (todo `075-pending-p3-handoff-branch-fragmentation`), not here.

---

## (Prior — FC68 / 083-W6 snapshot; retained point-in-time)

# HANDOFF — Sandbox · FC68 / 083-W6 RESOLVED (firebreak cwd-root anchor); merge-to-master decision pending

**Date:** 2026-07-22
**Active branch:** fix/fc68-firebreak-cwd-anchor @ 61dbbfb (+ a Compound commit this session) — pushed to origin; branched off origin/master @ a5cde9d
**Phase:** FC68 fix COMPLETE (Codex NO-GO→fix→GO, P0/P1/P2=0), Compound DONE. PENDING: Alex's fast-forward-merge-to-master decision (A vs B — see Deferred Items). Do NOT push origin/master without explicit approval.

## Current State

The active work is the **FC68 / 083-W6** structural fix — the last HIGH-severity deferred item from Run 083 (a silent firebreak fail-open when the orchestrator's cwd drifts into a worker worktree). COMPLETE on branch `fix/fc68-firebreak-cwd-anchor`: absolute `--root` + `realpath` canonicalization + **git-metadata main-worktree validation** (`git-dir == git-common-dir`), fail-closed exit 3; an exit-code-driven per-wave **read-back gate** in SKILL 9w.9.6; and the H5 gate-window toggle protocol (rejected a name-based `-m` carve-out). Codex re-review: **GO** (P0/P1/P2 = 0). 18 real-git-worktree tests; existing firebreak suites (classify 282 / gate 26 / soundness 448 / superset 297) unaffected. Solution: `docs/solutions/2026-07-22-fc68-firebreak-cwd-root-anchor.md`. **Both remaining Run-083 HIGH deferreds (083-W2, 083-W6) are now CLOSED.**

**Run 083 (swarmlimit 19-agent Max-Value Wave-Barrier Swarm) is COMPLETE** (record retained below): 19 build agents / 3 waves, C2 smoke 31/31, 0 P1 / 3 P2 deferred, PIPELINE_PASS_WITH_DEFERRED_RISK grade B. `origin/master` @ a5cde9d carries the full build + tail artifacts.

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
Read HANDOFF.md for context. This is sandbox, on branch fix/fc68-firebreak-cwd-anchor
(NOT feat/082 — that branch's Run-083 work is done and on origin/master @ a5cde9d).

FC68 / 083-W6 (firebreak cwd-root-drift fail-open) is RESOLVED: absolute --root +
realpath + git-metadata main-worktree validation (fail-closed exit 3), exit-code
per-wave read-back gate in SKILL 9w.9.6, H5 toggle protocol. Codex NO-GO→fix→GO
(P0/P1/P2=0). 18 real-worktree tests; existing firebreak suites unaffected.
Solution: docs/solutions/2026-07-22-fc68-firebreak-cwd-root-anchor.md.
agent-pitfalls FC68 Agent rule updated + Update Log row (2026-07-22 FC68 fix).

IMMEDIATE — the one open decision (needs Alex, do NOT execute unasked):
- Merge fix/fc68-firebreak-cwd-anchor → origin/master. Clean fast-forward from a5cde9d.
  A = full FF (includes unrelated docs-only c6a0d84 trust-gate readiness doc).
  B = FC68-only integration (a new branch off a5cde9d cherry-picking the FC68 + compound
      commits, excluding c6a0d84), then FF master to it.
  FF-push to master requires Alex's explicit approval.

STANDING (trust-gate for big UNATTENDED runs — see MEMORY unattended-big-run-trust-gate):
- P1 remainder: FC58 gate-python (H5) — toggle protocol now documented; allowlist still narrow.
- P3: build tools/verify_harvest.py (harvest gate is self-certified); fix check_compounded_darkness.py.
- P4: one ≥20-agent fully-unattended SKILL-driven run at 0 interventions → trusted baseline.
- Also: master declutter (FC59) needs Alex sign-off; G2/G4/G5 governance gaps.

INVARIANTS: firebreak deny-known-bad; Gate-8 fail-closed; builds namespace under own top-level dir (FC59);
self-audit-reviewer stays Sonnet; disconfirmer stays Opus; NEVER pay usage credits — Max subscription only.
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
