#!/usr/bin/env python3
"""Detect spec-provenance drift before a swarm spawns (FC52 detection).

Worker worktrees root on the repo's DEFAULT branch, NOT the orchestrator's
feature branch (FC51). So each worker reads `docs/plans/<spec>.md` as it exists
at the worktree base -- which is STALE if the spec was converged on the feature
branch after that base commit. The pre-swarm gates validated the FEATURE-BRANCH
spec; if the worktree-base spec differs, the gates certified an artifact the
workers will never read (FC52: gate/use provenance drift). Run 070: all 16
workers read a 2010-line stale spec while the gates validated the 2295-line
converged one -- missed only by luck.

Run 071 added the baseRef-fresh facet (FC52-BASEREF-FRESH-071): under Agent
isolation worktrees with baseRef=fresh, workers root on origin/<default>, not
the LOCAL default branch. A gate that verifies the local branch can issue a
false PROVENANCE_OK while workers consume a stale origin. When origin/<default>
exists, this detector resolves the comparison base to that remote-tracking ref
and warns when the local branch has unpushed commits.

This is the DETECTION half of autopilot SKILL Step 9w.9.5. It compares the spec's
git blob SHA on the two branches. It does NOT repair (the inline-injection repair
is agent judgment) -- it reports OK vs DRIFT so the orchestrator decides.

Share-not-fork: this is the SINGLE implementation of the compare. Step 9w.9.5
CALLS this script, and the F-D1 fixture invokes this SAME script. There is no
second copy that can drift from the shipped gate -- which is the whole point
(a fixture that tested a reimplementation would reproduce the FC52 drift it
exists to catch).

Exit codes (kept in 1-255; 256 would wrap to 0 = a false OK):
  0  PROVENANCE_OK     both branches carry the identical spec blob
  3  PROVENANCE_DRIFT  the blobs differ, or the spec exists on only one branch
  2  ERROR             a branch is missing, not a git repo, or the spec is on
                       neither branch (cannot establish provenance)
  5  BAD_ARGS          malformed CLI arguments

Usage:
  check_spec_provenance.py --default-branch <name> --original-branch <name>
      --spec-path docs/plans/<spec>.md [--repo <path>]
"""

import argparse
import subprocess
import sys

EXIT_OK = 0
EXIT_ERROR = 2
EXIT_DRIFT = 3
EXIT_BAD_ARGS = 5


class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on error, which collides with EXIT_ERROR. Override to 5."""

    def error(self, message):
        sys.stderr.write(f"STATUS: BAD_ARGS -- {message}\n")
        sys.exit(EXIT_BAD_ARGS)


def _git(repo: str, *args: str) -> subprocess.CompletedProcess:
    """Run a git command in `repo`, capturing output. Never raises on non-zero."""
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True, text=True,
    )


def _branch_exists(repo: str, branch: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "--quiet", f"{branch}^{{commit}}").returncode == 0


def _blob_sha(repo: str, branch: str, spec_path: str) -> str | None:
    """Blob SHA of spec_path at branch tip, or None if the file is absent there."""
    cp = _git(repo, "rev-parse", f"{branch}:{spec_path}")
    return cp.stdout.strip() if cp.returncode == 0 else None


def _resolve_base_ref(repo: str, default_branch: str):
    """Return (base_ref, warning) -- the ref worker worktrees actually root on.

    Under Agent isolation:"worktree" with baseRef=fresh, worktrees root on
    origin/<default>, NOT the local branch (FC52-BASEREF-FRESH-071). When the
    remote-tracking ref exists it is authoritative and the comparison runs
    against it. Falls back to the local branch when no remote-tracking ref
    exists (e.g. fixture repos with no remote -- keeps F-D1 behavior unchanged).
    """
    origin_ref = f"origin/{default_branch}"
    if not _branch_exists(repo, origin_ref):
        return default_branch, None
    warn = None
    local_tip = _git(repo, "rev-parse", default_branch).stdout.strip()
    origin_tip = _git(repo, "rev-parse", origin_ref).stdout.strip()
    if local_tip != origin_tip:
        warn = (f"local {default_branch} ({local_tip[:7]}) != {origin_ref} "
                f"({origin_tip[:7]}) -- unpushed local commits; workers consume "
                f"{origin_ref} under baseRef=fresh. Push before spawn.")
    return origin_ref, warn


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description="Detect spec-provenance drift before swarm spawn.")
    parser.add_argument("--default-branch", required=True,
                        help="branch the worker worktrees root on (e.g. master)")
    parser.add_argument("--original-branch", required=True,
                        help="orchestrator's feature branch (the gated spec)")
    parser.add_argument("--spec-path", required=True,
                        help="repo-relative spec path, e.g. docs/plans/<spec>.md")
    parser.add_argument("--repo", default=".", help="path to the git repo (default: cwd)")
    args = parser.parse_args(argv)

    if not _git(args.repo, "rev-parse", "--git-dir").returncode == 0:
        sys.stderr.write(f"STATUS: ERROR -- not a git repo: {args.repo}\n")
        return EXIT_ERROR
    for branch in (args.default_branch, args.original_branch):
        if not _branch_exists(args.repo, branch):
            sys.stderr.write(f"STATUS: ERROR -- branch not found: {branch}\n")
            return EXIT_ERROR

    base_ref, base_warn = _resolve_base_ref(args.repo, args.default_branch)
    if base_warn:
        sys.stderr.write(f"WARNING: {base_warn}\n")
    base_sha = _blob_sha(args.repo, base_ref, args.spec_path)
    feat_sha = _blob_sha(args.repo, args.original_branch, args.spec_path)

    if base_sha is None and feat_sha is None:
        sys.stderr.write(
            f"STATUS: ERROR -- spec absent on both branches: {args.spec_path}\n"
        )
        return EXIT_ERROR

    # Drift = the worktree-base spec is not byte-identical to the gated spec.
    # A spec present on only one branch is the strongest form of drift (workers
    # would read a missing/different file than the gates validated).
    if base_sha == feat_sha:
        print(f"STATUS: PROVENANCE_OK -- {args.spec_path}")
        print(f"default({base_ref})={base_sha} == "
              f"original({args.original_branch})={feat_sha}")
        return EXIT_OK

    print(f"STATUS: PROVENANCE_DRIFT -- {args.spec_path}")
    print(f"default({base_ref})={base_sha or 'ABSENT'} != "
          f"original({args.original_branch})={feat_sha or 'ABSENT'}")
    return EXIT_DRIFT


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # fail-closed: an unexpected crash must never read as OK
        sys.stderr.write(f"STATUS: ERROR -- unexpected error: {exc}\n")
        sys.exit(EXIT_ERROR)
