---
title: Track A P-extract — cherry-pick assembly → shared do-it tool
date: 2026-06-09
branch: feat/track-a-pextract-cherrypick
status: planned
swarm: false
feed_forward:
  risk: "A mutating git tool that leaves a dirty tree or moves HEAD unexpectedly on a partial-conflict path, mis-attributing an ownership escape as a clean pick (or vice-versa)."
  verify_first: true
---

# Plan — Track A P-extract (cherry-pick assembly → `tools/assemble_worker.py`)

## Context

Track A (FC51 cherry-pick assembly) is the per-worker logic in
`.claude/agents/swarm-runner.md` **Step 3 (lines 76–138)**. It is field-proven
(runs 069 + 070, 0 conflicts) and spike-validated, but lives as **agent-prose** —
so it is the one hardening track with no real `EXERCISED` fixture row, and the
load-bearing `git cherry-pick <base>..<branch>` range command (whose `<branch>^`
mis-form is the FC51 silent-data-loss class) is not under test.

This plan extracts that per-worker logic into a shared **"do-it" CLI tool** that
BOTH `swarm-runner` calls AND the fixture suite exercises (share-not-fork, the
same pattern as `tools/check_spec_provenance.py`). Design is Codex-reviewed
(`docs/handoffs/2026-06-09-track-a-pextract-codex-design.md`, GO).

## The 4-Question Quality Gate

1. **What exactly is changing?**
   - NEW `tools/assemble_worker.py` — a single-worker git assembly primitive that
     performs one worker's cherry-pick and reports a structured `STATUS:` + exit code.
   - NEW F-A1 fixture (`eval-harness/fixtures/fa1/`) + a new row in
     `eval-harness/validate_hardening.py` that exercises the real tool against a
     hermetic temp repo (earns Track A its `EXERCISED` row).
   - EDIT `.claude/agents/swarm-runner.md` Step 3 — replace the inline git prose with
     a call to the tool per worker, branching on its `STATUS`. swarm-runner KEEPS the
     loop, COMPLETED/skip filtering, BUILD_TRACKING row appends, assembly summary, and
     the conflict→preserve-branches→abort orchestration.

2. **What must NOT change?**
   - The **O3 invariant**: base = `git merge-base <original_branch> <branch>` (the
     same base the ownership gate used). The tool must compute the identical base.
   - The full-range replay semantics: ALL N worker commits replayed via
     `<base>..<branch>`. `<branch>^` remains FORBIDDEN.
   - The **conflict = ownership-gate ESCAPE** policy: never resolve inline; preserve
     all worker branches; leave `original_branch` untouched; swarm-runner writes the
     `assembly-ownership-conflict.md` report and sets `final_status: FAIL`.
   - BUILD_TRACKING/report writing stays in swarm-runner (the tool emits metadata only).
   - Detached-HEAD remains out of scope (parity with current prose).
   - swarm-runner Steps 1, 2, 4–9 (plan read, assembly-branch checkout, contract/
     smoke/test/merge/cleanup) are untouched.

3. **How will we know it worked?** — see Acceptance Tests below (EARS + commands).

4. **Most likely way this plan is wrong?** — see Feed-Forward. The risk is the
   mutation/cleanup contract on the partial-conflict path: a tool that aborts but
   leaves a dirty tree or moved HEAD, or that classifies a real ownership escape as
   a clean pick. The fixture's clean-tree + all-N-commits assertions are the
   verify-first guard.

## Tool contract (Codex-locked)

**CLI:** `tools/assemble_worker.py --repo <path> --original-branch <name>
--assembly-branch <name> --worker-branch <name>`

- `--assembly-branch` is an **assertion guard**, NOT a checkout instruction: the
  tool verifies `git -C <repo> branch --show-current` == `<assembly-branch>` and
  errors otherwise. The caller (swarm-runner Step 2) is responsible for the checkout.

**Behavior (single worker):**
1. Pre-conditions: repo valid; HEAD is `<assembly-branch>`; working tree clean
   (`git status --porcelain` empty). Capture `pre_pick_head = git rev-parse HEAD`.
2. `base = git merge-base <original_branch> <worker-branch>`.
3. Pre-flight: `git rev-list --merges <base>..<worker-branch>` non-empty →
   `OWNERSHIP_CONFLICT -- pre-flight: merge commit on <worker-branch>`.
4. `count = git rev-list --count <base>..<worker-branch>`; if 0 → `EMPTY_DELTA`.
5. `git cherry-pick <base>..<worker-branch>`:
   - success → assert tree clean and HEAD advanced from `pre_pick_head` →
     `PICKED -- base=<sha> commit=<new_head_sha> count=<n>`.
   - conflict → `git cherry-pick --abort`; assert tree clean AND HEAD ==
     `pre_pick_head`; if either assertion fails → `ERROR -- <reason>`; else
     `OWNERSHIP_CONFLICT -- cherry-pick conflict on <worker-branch>`.

**Status / exit contract (line 1 = `STATUS:`):**
| STATUS | Exit | Meaning |
|--------|------|---------|
| `PICKED -- base=<sha> commit=<sha> count=<n>` | 0 | clean replay of all N commits |
| `EMPTY_DELTA -- base=<sha>` | 0 | zero commits; no-op (not an error) |
| `OWNERSHIP_CONFLICT -- <reason>` | nonzero | merge-commit pre-flight OR cherry-pick conflict; tree restored clean |
| `ERROR -- <reason>` | nonzero | bad repo/branch, dirty entry state, HEAD mismatch, abort-cleanup failure, unexpected git failure |

The tool guarantees its OWN post-abort clean state. It does NOT perform run-level
rollback (that policy stays with the orchestrator).

## Acceptance Tests (EARS)

### Happy path
- WHEN a COMPLETED worker branch carries N≥1 commits on the fork-point base and the
  delta does not overlap another worker THE SYSTEM SHALL cherry-pick all N commits
  onto the assembly branch and emit `STATUS: PICKED -- base=<sha> commit=<sha>
  count=<N>` with exit 0.
- WHEN a worker branch has zero commits beyond the fork-point base THE SYSTEM SHALL
  make no change and emit `STATUS: EMPTY_DELTA -- base=<sha>` with exit 0.

### Error / escape cases
- WHEN a worker's cherry-pick conflicts THE SYSTEM SHALL run `git cherry-pick
  --abort`, restore a clean tree at the original HEAD, and emit `STATUS:
  OWNERSHIP_CONFLICT -- cherry-pick conflict on <branch>` with nonzero exit.
- WHEN a worker branch contains a merge commit in its delta THE SYSTEM SHALL emit
  `STATUS: OWNERSHIP_CONFLICT -- pre-flight: merge commit on <branch>` with nonzero
  exit and make no change.
- WHEN the current branch is not `<assembly-branch>` OR the working tree is dirty on
  entry THE SYSTEM SHALL emit `STATUS: ERROR -- <reason>` with nonzero exit and make
  no change.
- WHEN a multi-commit worker is assembled THE SYSTEM SHALL replay the EARLIEST commit
  too (negative control: the `<branch>^` form would drop it — the fixture asserts the
  earliest commit's content is present).

### Verification commands
- `python tools/assemble_worker.py --repo /tmp/fa1 --original-branch master --assembly-branch asm --worker-branch w-multi | head -1` → starts with `STATUS: PICKED`
- `eval-harness/.venv/bin/python3 eval-harness/validate_hardening.py` → Track A row reads `EXERCISED` and overall exit 0
- F-A1 self-checks (inside the harness): all 4 cases assert expected STATUS; the
  multi-commit case asserts ALL N commits' content present in the assembly tree.

## F-A1 fixture cases (Codex-locked)

| Case | Worker shape | Asserts |
|------|--------------|---------|
| A1 | 2-commit worker, first commit load-bearing | both commits replayed; earliest commit's content present (negative control vs `<branch>^`) |
| A2 | zero-commit worker | `EMPTY_DELTA` |
| A3 | conflicting worker (edits a line another path owns) | `OWNERSHIP_CONFLICT`; clean tree after abort |
| A4 | merge-commit worker | `OWNERSHIP_CONFLICT -- pre-flight: merge commit ...` |

**Fixture isolation (hermetic temp repo):** temp repo path only; local
`user.name`/`user.email`; `GIT_CONFIG_NOSYSTEM=1`; `GIT_CONFIG_GLOBAL=/dev/null`;
`HOME`/`XDG_CONFIG_HOME` → temp dirs; `GIT_TERMINAL_PROMPT=0`;
`core.hooksPath=/dev/null`; `commit.gpgsign=false`.

## Build sequence (incremental commits)

1. `tools/assemble_worker.py` — the tool (one concern; ~committable alone).
2. F-A1 fixture builder + cases + `validate_hardening.py` wiring (Track A → EXERCISED).
3. `swarm-runner.md` Step 3 rewire to call the tool (share-not-fork).
4. (Separate) scoped real-orchestrator validation — prove the agent→tool wiring in
   the actual pipeline path (like the FC52 `998854e` pre-spawn-halt run).
5. Compound: solution doc + learnings; refine the Track A row in HANDOFF + the
   fixture README fidelity table.

## Feed-Forward
- **Hardest decision:** "do-it" (mutating) tool vs "compute-only" planner. Chose
  do-it so the load-bearing range command is under test — a compute-only tool would
  leave the data-loss-prone `git cherry-pick` in prose, defeating the purpose.
- **Rejected alternatives:** keep Track A as `P-accept` prose (rejected: leaves the
  range command untested and the suite's coverage incomplete, blocking #3 adoption);
  tool checks out the assembly branch itself (rejected per Codex: hides HEAD movement
  in the primitive — caller owns checkout, tool only asserts); fold detached-HEAD
  handling in now (rejected: widens the primitive beyond the P-extract target).
- **Least confident:** the partial-conflict cleanup contract under real git edge
  cases (e.g., a cherry-pick that conflicts on a later commit after earlier ones
  already applied). Mitigation: the tool asserts HEAD == pre-pick HEAD after abort
  (not merely "tree clean"), and F-A1 case A3 exercises exactly this; a non-restored
  HEAD returns ERROR, never a false PICKED/CONFLICT.
