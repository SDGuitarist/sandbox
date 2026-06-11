# Codex Code-Review Handoff — Track A P-extract (Work phase)

**Type:** Binding code review (post-Work). Design was already Codex-approved; this
reviews the IMPLEMENTATION.
**Date:** 2026-06-09
**Repo:** `~/Projects/sandbox`
**Branch:** `feat/track-a-pextract-cherrypick` (pushed). Review range: `master..HEAD`
= commits `7f2d9db..18a3784` (6 commits).

**Follow-ups already applied since this handoff was first drafted (review the final
state, all on-branch):**
- `bf304c9` — made swarm-runner Step 3 / Output Contract exhaustive: added the
  `assembly-error.md` blocking example; Step 3 **case 5** folds the tool's `BAD_ARGS`/
  exit 5 and ANY unrecognized result into the `assembly-error:` blocking path
  fail-closed; Rule 2 updated to three blocking classes.
- `18a3784` — **risk #1 fix:** the tool now prints its `STATUS:` line to **stdout as
  line 1 in every case** (previously OWNERSHIP_CONFLICT/ERROR/BAD_ARGS went to
  stderr). swarm-runner now documents the stdout-line-1 guarantee. Please confirm
  this is sound and that no caller path still assumes the old split.

---

## Read first (project context)

- `HANDOFF.md`
- `CLAUDE.md` (operating contract — esp. Forbidden Actions, Bash Command Rules)
- `docs/plans/2026-06-09-track-a-pextract-plan.md` (the spec this implements; 4-question
  gate + EARS acceptance tests)
- `docs/handoffs/2026-06-09-track-a-pextract-codex-design.md` (your prior design verdict)

## Files changed (the review surface)

| File | Change |
|------|--------|
| `tools/assemble_worker.py` | NEW — the single-worker "do-it" cherry-pick primitive (mutates git) |
| `eval-harness/validate_hardening.py` | NEW F-A1 fixture (5 cases, hermetic temp repos) + retired Track A static row + registry/docstring |
| `.claude/agents/swarm-runner.md` | Step 3 rewired to CALL the tool; new `assembly-error:` blocking class (Rule 2) |

## What it implements (design recap)

A do-it tool so the load-bearing `git cherry-pick <base>..<branch>` range command
lives in tested code, not swarm-runner prose (the `<branch>^` form is the FC51
silent-data-loss class). `--assembly-branch` is an assertion guard (caller owns
checkout). Status/exit contract:

| STATUS | Exit | Meaning |
|--------|------|---------|
| `PICKED -- base=<sha> commit=<sha> count=<n>` | 0 | clean replay of all N commits |
| `EMPTY_DELTA -- base=<sha>` | 0 | zero-commit no-op |
| `OWNERSHIP_CONFLICT -- <reason>` | 3 | merge-commit pre-flight OR cherry-pick conflict; tree restored clean |
| `ERROR -- <reason>` | 2 | bad repo/branch, dirty entry, HEAD mismatch, abort-cleanup failure, non-conflict cherry-pick failure |
| `BAD_ARGS -- <msg>` | 5 | malformed CLI |

F-A1 exercises the SHIPPED tool (share-not-fork) on five shapes: A1 multi-commit
(asserts all N replayed — negative control for `<branch>^`), A2 empty, A3 conflict
(asserts clean tree + no pick in progress after abort), A4 merge-commit pre-flight,
A5 wrong-branch ERROR (no mutation). All 5 PASS; F-D1/F-C1 re-confirmed.

## Focus areas (ordered)

1. **Mutation / cleanup correctness (the Feed-Forward risk).** In
   `tools/assemble_worker.py`, scrutinize the non-zero cherry-pick path: is the
   conflict-vs-unexpected classification (`--diff-filter=U` unmerged check) correct?
   Can any real git state slip through where the tool returns PICKED/CONFLICT while
   the tree is actually dirty or HEAD moved? Is the post-abort assertion (tree clean
   AND HEAD == pre_pick_head) sufficient, or is there a sequence (e.g. conflict on a
   LATER commit after earlier ones applied; `--abort` partial failure) that defeats
   it? Should it also guard against an in-progress REVERT/MERGE state on entry?
2. **Pre-flight / classification edge cases.** `git rev-list --merges <base>..<branch>`
   for merge detection; `--count` for empty. Any worker shape (octopus merge, root
   commit, orphan branch, base == branch tip, force-pushed worker) that mis-classifies?
   Is folding merge-commit into OWNERSHIP_CONFLICT (vs ERROR) the right call?
3. **Exit-code discipline.** Codes kept in 1–255 (no 256 wrap to a false 0)? argparse
   error remapped to 5 (not 2, which would collide with ERROR)? Any path that prints a
   STATUS line but returns the wrong code, or vice versa?
4. **swarm-runner wiring (share-not-fork integrity).** Does Step 3 now branch
   correctly on ALL of PICKED/EMPTY_DELTA/OWNERSHIP_CONFLICT/ERROR? Is the new
   `assembly-error:` blocking class consistent across Step 3, Rule 2, and the summary
   (Step 9)? Any place still assuming the old inline behavior? Is `python
   tools/assemble_worker.py --repo .` the right invocation given swarm-runner's cwd
   and Bash rules (one command per call, no chaining)?
5. **Fixture soundness (F-A1).** Is the hermetic isolation (`GIT_CONFIG_NOSYSTEM`,
   `GIT_CONFIG_GLOBAL=/dev/null`, temp HOME/XDG, hooks/signing off) actually leak-proof
   on a dev box with a global gitconfig? Could any case pass for the WRONG reason
   (e.g. A3 "conflict" that's really an unrelated failure; A1 passing without truly
   proving full-range replay)? Is the EXERCISED label honest (it runs the real
   `tools/` script, no reimplementation)?
6. **Honesty-contract regressions.** TRACK_STATIC is now empty and the docstring
   claims all four tracks fixtured — does the matrix still render correctly for a
   single-fixture invocation and the full run? Any case where Track A could show a
   fidelity it didn't earn?
7. **CLAUDE.md compliance.** The tool runs `git cherry-pick` (mutation). Does it stay
   within Forbidden Actions (no force-push, no reset --hard, no history rewrite of
   published commits)? It only mutates a local assembly branch the caller created — confirm.

## Known NOT done (don't flag as gaps — they're scoped follow-ons)

- Full 2-agent suite run (F-B1/F-B2 paid calls) — not run this phase; B code untouched.
- Scoped real-orchestrator validation of the agent→tool wiring (plan step 4) — pending.
- Detached-HEAD first-class handling — deliberately out of scope (falls through to
  EMPTY_DELTA), per your design verdict Q5.

## Output we want

Findings ordered by severity (P1/P2/P3), each with the exact file:line and a minimal
fix. Then a Claude Code fix prompt that instructs Claude Code to: (1) apply the
fixes, (2) run a SECOND self-review of its own changes, (3) re-run the affected
fixtures, and (4) report any remaining risks before the task is considered complete.
Confirm **GO** if no blocking findings.
