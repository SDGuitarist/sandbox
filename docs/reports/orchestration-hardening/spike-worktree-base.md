# Phase-0 Spike — Worktree Base Divergence (Track A)

**Date:** 2026-06-07
**Plan:** `docs/plans/2026-06-07-refactor-autopilot-orchestration-hardening-plan.md`
**Gate:** MANDATORY before any Track A edit (`SKILL.md:647` / `swarm-runner.md`).
**Scripts:** `spike-worktree-base.sh` (comprehensive, 16/16 PASS), `spike-ownership.sh`
(1/1 PASS), `spike-conflict.sh` (5/5 PASS). All self-contained throwaway repos
under `mktemp`, no real data touched.

## What was simulated

The verified harness fact (Run 069 assembly-summary): worker worktrees are rooted
on the repo **default branch** (`master`, `f90aed8`), NOT on the orchestrator's
feature HEAD. The spike builds: `master` → `feat` (original_branch, 2 commits
ahead) → workers branched off `master` (divergent base), plus an is-ancestor
worker off `feat`, an empty worker, two same-file conflict workers, a merge-commit
worker, and a detached HEAD.

## Q1 — Is `merge-base(original_branch, worker)` the true fork point? (RESOLVED: yes)

| Assertion | Evidence |
|-----------|----------|
| `merge-base(feat, w1) == master` | the divergent worker's real fork point IS the merge-base |
| `git diff --name-only feat...w1` lists **only** `w1.txt` | three-dot ownership attributes only the worker delta — no feat/master noise (this is why the fix is a one-token `main`→`original_branch`, keeping the three-dot operator) |
| `cherry-pick merge-base..w3` replays **all 3** commits | full N-commit fidelity |
| `merge-base..w3` range = 3 vs `w3^..w3` range = **1** | confirms `<branch>^` silently drops earlier commits (the FC51 data-loss class) → eliminated |
| zero-commit `w0`: `merge-base..w0` range = **0** | degrades to a clean no-op, not an error |
| ownership-base == cherry-pick-base for `w1` | the **O3 invariant**: gate and assembly compute an identical base |

## Q2 — Assembly routing (RESOLVED)

| Assertion | Evidence |
|-----------|----------|
| disjoint divergent `wca` → clean cherry-pick onto `feat` | the happy path |
| same-file `wcb` → cherry-pick **conflicts** | detected via porcelain `^[UAD]{2}` marker |
| `git cherry-pick --abort` → **clean tree** | `status --porcelain` empty |
| worker branches `wca`/`wcb` **preserved** | no Step-8 cleanup on abort (matches existing abort classes) |
| `original_branch` (feat) HEAD **unchanged** | assembly never merged to feat on abort |

A cherry-pick conflict under enforced disjoint ownership (Step 10.5w) can ONLY
mean an ownership-gate escape. So the conflict path must NOT invoke the inline
spec resolution (`swarm-runner.md:85-93`) — that would fabricate a resolution and
mask the violation. It aborts and records `assembly-ownership-conflict:`.

## Strategy decision (i vs ii) — CHOSEN: **(i) uniform cherry-pick**

| Assertion | Evidence |
|-----------|----------|
| is-ancestor worker `wm`: cherry-pick **TREE == merge --no-ff TREE** | uniform cherry-pick reproduces the mergeable result exactly — no regression |
| empty worker: cherry-pick no-op leaves tree == `feat` tree | matches the merge no-op |

**Decision: strategy (i) — uniform `git cherry-pick $(git merge-base <original_branch> <worker>)..<worker>` for every COMPLETED worker**, onto an assembly branch cut from `original_branch` HEAD. Rationale:

1. **The spike proves (i) reproduces (ii)'s tree** for both the is-ancestor and empty edge cases — the exact condition the plan set for choosing (i) over the default (ii).
2. **069 evidence:** uniform cherry-pick is literally what ran clean (24/24 workers, **0 conflicts**, per `docs/reports/069/assembly-summary.md`). Strategy (ii)'s per-worker `merge --no-ff` is **dead code** in the harness's divergent-base reality — no worker is ever `is-ancestor` of `feat`, so the merge branch never fires.
3. **One code path** = simpler, fewer failure modes.

**Untouched:** the final assembly→`original_branch` merge-back stays `git merge --no-ff` (required by the plan's "must NOT change" guard). Because the assembly branch is `feat` + disjoint cherry-picks, `feat` is an ancestor of it, so the merge-back cannot conflict.

### Blocking-class bookkeeping — FINALIZED in Phase 3

Strategy (i) removes the **per-worker** merge, so the per-worker `merge-conflict:`
trigger is replaced by `assembly-ownership-conflict:`. **Phase-3 finding (verified
against the real file):** `merge-conflict:` was ONLY ever raised in the per-worker
merge (swarm-runner Step 3, old lines 89–93). The merge-back (Step 7,
`swarm-runner.md:131`) calls `git merge --no-ff <assembly_branch>` but has **no
conflict handler today** and cannot conflict anyway (the assembly branch is
`original_branch` + disjoint cherry-picks, so `original_branch` is its ancestor →
fast-forwardable). So `merge-conflict:` is **fully retired and replaced** by
`assembly-ownership-conflict:` — **count stays 2** (`contract-check:` +
`assembly-ownership-conflict:`), exactly the plan's strategy-(i) prescription. The
merge-back keeps its status-quo behavior (no named class, fails via disk-verify if
it ever broke) — NOT a regression. Propagated to: swarm-runner Rule 2 + Output
Contract, and the orchestrator's wire-abort handler (`SKILL.md` ~723, ~779).
Verified: no hardcoded enum in self-audit WARN handling rejects the changed set.

## Out-of-scope states — pre-flight aborts loudly (VERIFIED)

| State | Detection | Evidence |
|-------|-----------|----------|
| detached HEAD | `git rev-parse --abbrev-ref HEAD` == `HEAD` | detected |
| merge-commit worker | `git rev-list --merges <merge-base>..<branch>` non-empty | detected (count 1) |

The harness produces linear, single-author worker branches; these states are not
first-class. The assembly pre-flight aborts on them rather than mis-attributing or
silently dropping changes. The spike confirms detection fires; it does not handle them.

## Exit criterion — MET

- [x] Both questions answered with evidence (16/16 comprehensive assertions).
- [x] Strategy chosen: **(i) uniform cherry-pick** (proven to reproduce the merge tree + matches 069's clean run).
- [x] Ownership-base == cherry-pick-base confirmed identical (O3 invariant).
- [x] merge-commit / detached-HEAD pre-flight verified to abort.

**Track A is unblocked.** Phase 3 may edit `SKILL.md:647` (one token) and
`swarm-runner.md` (cherry-pick recipe + `assembly-ownership-conflict:` class +
class bookkeeping + COMPLETED-only scope + the two pre-flight aborts).
