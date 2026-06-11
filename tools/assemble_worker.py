#!/usr/bin/env python3
"""Assemble ONE swarm worker's commits onto the assembly branch (Track A / FC51).

Worker worktrees root on the repo's DEFAULT branch, NOT the orchestrator's feature
branch, so each worker branch carries only its own commits on a divergent base. The
assembly step replays each COMPLETED worker's fork-point delta onto the assembly
branch via `git cherry-pick <base>..<branch>` -- replaying ALL N commits. The
`<branch>^` form is the FC51 silent-data-loss class: it drops every commit before the
last on a multi-commit worker. This tool exists so that load-bearing range command
lives in TESTED code, not agent prose.

This is the per-worker PRIMITIVE for autopilot swarm-runner Step 3. The orchestrator
(swarm-runner) keeps the loop, COMPLETED/skip filtering, BUILD_TRACKING bookkeeping,
the assembly summary, and the conflict->preserve-branches abort policy. This tool does
exactly one worker and reports a structured STATUS; it emits metadata only and never
writes reports or does run-level rollback.

Share-not-fork: this is the SINGLE implementation of the assembly cherry-pick. Step 3
CALLS this script and the F-A1 fixture invokes this SAME script -- no second copy that
can drift from the shipped behavior (a fixture testing a reimplementation would prove
nothing about the real path).

Mutation contract:
  - The CALLER checks out the assembly branch. `--assembly-branch` is an ASSERTION
    GUARD: the tool verifies HEAD is that branch and refuses to run otherwise. The
    tool never checks out a branch (no hidden HEAD movement in the primitive).
  - The tool guarantees its OWN clean exit: on a conflict it aborts the cherry-pick
    and verifies the tree is clean AND HEAD is restored to the pre-pick commit. If it
    cannot restore that state, it returns ERROR (never a false PICKED/CONFLICT).

Output: the `STATUS:` line is ALWAYS printed to STDOUT as line 1, in every case
(success or failure), and the exit code mirrors it. The caller can read line 1 of
stdout for the verdict without merging stderr -- there is no STATUS-on-stderr split.

Exit codes (kept in 1-255; 256 would wrap to 0 = a false success):
  0  PICKED / EMPTY_DELTA   clean replay of all N commits, or a zero-commit no-op
  2  ERROR                  bad repo/branch, dirty entry state, HEAD/branch mismatch,
                            abort-cleanup failure, or unexpected git failure
  3  OWNERSHIP_CONFLICT     a merge commit in the delta (pre-flight) OR a cherry-pick
                            conflict -- an ownership-gate ESCAPE; tree restored clean
  5  BAD_ARGS               malformed CLI arguments

Usage:
  assemble_worker.py --repo <path> --original-branch <name>
      --assembly-branch <name> --worker-branch <name>
"""

import argparse
import subprocess
import sys

EXIT_OK = 0
EXIT_ERROR = 2
EXIT_CONFLICT = 3
EXIT_BAD_ARGS = 5


class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on error, which collides with EXIT_ERROR. Override to 5."""

    def error(self, message):
        print(f"STATUS: BAD_ARGS -- {message}")  # STATUS always to stdout
        sys.exit(EXIT_BAD_ARGS)


def _git(repo: str, *args: str) -> subprocess.CompletedProcess:
    """Run a git command in `repo`, capturing output. Never raises on non-zero."""
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def _branch_exists(repo: str, branch: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "--quiet", f"{branch}^{{commit}}").returncode == 0


def _current_branch(repo: str) -> str:
    """The checked-out branch name, or '' on detached HEAD / error."""
    return _git(repo, "branch", "--show-current").stdout.strip()


def _tree_clean(repo: str) -> bool:
    cp = _git(repo, "status", "--porcelain")
    return cp.returncode == 0 and cp.stdout.strip() == ""


def _head_sha(repo: str) -> str | None:
    cp = _git(repo, "rev-parse", "HEAD")
    return cp.stdout.strip() if cp.returncode == 0 else None


def _cherry_pick_in_progress(repo: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "--quiet", "CHERRY_PICK_HEAD").returncode == 0


def _err(message: str) -> int:
    print(f"STATUS: ERROR -- {message}")  # STATUS always to stdout
    return EXIT_ERROR


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description="Assemble one swarm worker via cherry-pick (Track A).")
    parser.add_argument("--repo", default=".", help="path to the git repo (default: cwd)")
    parser.add_argument("--original-branch", required=True,
                        help="branch the worker forked from (cherry-pick base source)")
    parser.add_argument("--assembly-branch", required=True,
                        help="assertion guard: HEAD MUST already be this branch")
    parser.add_argument("--worker-branch", required=True,
                        help="the COMPLETED worker branch to assemble")
    args = parser.parse_args(argv)

    # --- Pre-conditions (no mutation happens unless these all hold) -------------
    if _git(args.repo, "rev-parse", "--git-dir").returncode != 0:
        return _err(f"not a git repo: {args.repo}")
    for branch in (args.original_branch, args.worker_branch):
        if not _branch_exists(args.repo, branch):
            return _err(f"branch not found: {branch}")

    current = _current_branch(args.repo)
    if current != args.assembly_branch:
        return _err(
            f"HEAD is not the assembly branch (expected {args.assembly_branch!r}, "
            f"on {current or 'DETACHED'!r}); caller must check it out first"
        )
    if not _tree_clean(args.repo):
        return _err("working tree not clean on entry; refusing to cherry-pick")

    pre_pick_head = _head_sha(args.repo)
    if pre_pick_head is None:
        return _err("could not resolve HEAD on the assembly branch")

    base_cp = _git(args.repo, "merge-base", args.original_branch, args.worker_branch)
    if base_cp.returncode != 0:
        return _err(
            f"no merge-base between {args.original_branch} and {args.worker_branch}: "
            f"{base_cp.stderr.strip()}"
        )
    base = base_cp.stdout.strip()
    rng = f"{base}..{args.worker_branch}"

    # --- Pre-flight: a merge commit in the delta is an ownership escape ---------
    merges = _git(args.repo, "rev-list", "--merges", rng)
    if merges.returncode != 0:
        return _err(f"rev-list --merges failed: {merges.stderr.strip()}")
    if merges.stdout.strip():
        print(
            f"STATUS: OWNERSHIP_CONFLICT -- pre-flight: merge commit on {args.worker_branch}"
        )
        return EXIT_CONFLICT

    # --- Zero-commit no-op ------------------------------------------------------
    count_cp = _git(args.repo, "rev-list", "--count", rng)
    if count_cp.returncode != 0:
        return _err(f"rev-list --count failed: {count_cp.stderr.strip()}")
    count = count_cp.stdout.strip()
    if count == "0":
        print(f"STATUS: EMPTY_DELTA -- base={base}")
        return EXIT_OK

    # --- Cherry-pick the FULL fork-point range (all N commits) ------------------
    pick = _git(args.repo, "cherry-pick", rng)
    if pick.returncode == 0:
        new_head = _head_sha(args.repo)
        if not _tree_clean(args.repo):
            return _err("tree not clean after a 'successful' cherry-pick")
        if new_head is None or new_head == pre_pick_head:
            return _err("cherry-pick reported success but HEAD did not advance")
        print(f"STATUS: PICKED -- base={base} commit={new_head} count={count}")
        return EXIT_OK

    # --- Non-zero cherry-pick: classify conflict vs unexpected, then restore ----
    unmerged = _git(args.repo, "diff", "--name-only", "--diff-filter=U").stdout.strip()
    pick_stderr = pick.stderr.strip()

    if _cherry_pick_in_progress(args.repo):
        abort = _git(args.repo, "cherry-pick", "--abort")
        if abort.returncode != 0:
            return _err(f"cherry-pick --abort failed: {abort.stderr.strip()}")

    # The tool's clean-exit guarantee: tree clean AND HEAD restored to pre-pick.
    if not _tree_clean(args.repo) or _head_sha(args.repo) != pre_pick_head:
        return _err("could not restore clean pre-pick state after a failed cherry-pick")

    if unmerged:
        print(
            f"STATUS: OWNERSHIP_CONFLICT -- cherry-pick conflict on {args.worker_branch}"
        )
        return EXIT_CONFLICT

    # Non-conflict cherry-pick failure (e.g. would-be-empty commit) -- not an
    # ownership escape; surface it as ERROR so it is never mistaken for a clean pick.
    return _err(f"cherry-pick failed without conflict on {args.worker_branch}: {pick_stderr}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # fail-closed: an unexpected crash must never read as success
        print(f"STATUS: ERROR -- unexpected error: {exc}")  # STATUS always to stdout
        sys.exit(EXIT_ERROR)
