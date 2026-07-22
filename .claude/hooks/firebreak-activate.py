#!/usr/bin/env python3
"""G1 firebreak -- sentinel lifecycle (orchestrator-only, deterministic).

The PreToolUse classifier is a NO-OP unless `<repo_root>/.claude/firebreak-active.json`
exists (manual sessions untouched). The autopilot orchestrator calls this to write
that sentinel after the pre-spawn provenance gate / before worker spawn, flip its
phase before the tail-runner spawn, and remove it at run end.

Usage (always ONE command, never `python3 -c`):
  firebreak-activate.py activate <run_id> [project_key] [phase] [test_allowlist_json] [--root <abs>]
  firebreak-activate.py set-phase <phase> [--root <abs>]
  firebreak-activate.py deactivate [--root <abs>]
  firebreak-activate.py status [--root <abs>]

`activate` clears any stale sentinel first (a crashed prior run can leave one),
then writes a fresh record at the MAIN repo root.

Root anchoring (FC68 / 083-W6 -- the fix). The sentinel MUST land at the MAIN repo
root's `.claude/` so that sibling-wave workers -- which discover it by walking UP
from their own worktree cwd (firebreak-classify.py `find_sentinel`) -- can find it.
This tool no longer derives the root from the CURRENT WORKING DIRECTORY: the old
`git rev-parse` in cwd let an orchestrator whose cwd drifted into a lingering worker
worktree silently write the sentinel to the WRONG root, so the main-repo sentinel
was ABSENT and the next wave spawned UNGOVERNED -- a silent fail-open of the primary
safety control. Resolution order instead:
  1. --root <abs> (PREFERRED): the orchestrator passes the known main-repo path.
     Immune to cwd drift AND to which on-disk copy of this script executed (worktrees
     carry their own tracked copy). Must be ABSOLUTE -- a relative value is rejected
     (it would re-introduce cwd coupling).
  2. __file__ anchor: this file lives at <repo>/.claude/hooks/, so the repo root is
     two directory levels up from the hooks dir.
The candidate is realpath-canonicalized (defeating symlink aliases + case variants)
and then VALIDATED with GIT METADATA, pathname-independently: it must be a git
worktree TOP-LEVEL whose `--git-dir` == `--git-common-dir` (i.e. the MAIN worktree,
not a linked one -- a linked worktree placed ANYWHERE, not just under
.claude/worktrees/, is rejected) and must carry .claude/hooks/firebreak-classify.py.
The tool FAILS CLOSED (loud stderr + non-zero exit, NO sentinel written) on any
validation failure -- converting the old silent wrong-root write into a hard refuse.

Exit 0 on success; 2 usage error; 3 fail-closed root refusal; 1 operational error.
"""
import json
import os
import subprocess
import sys

SENTINEL_REL = os.path.join(".claude", "firebreak-active.json")
DEFAULT_TEST_ALLOWLIST = {"pytest": True}


def _git(root, *args):
    """`git -C root <args>` -> stripped stdout, or None on any failure (fail closed:
    a broken/absent git yields None, which the caller treats as a refusal)."""
    try:
        out = subprocess.run(["git", "-C", root, *args],
                             capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _resolve_git_path(root, p):
    """Canonicalize a git-reported path (which may be relative to `root`)."""
    if p is None:
        return None
    return os.path.realpath(p if os.path.isabs(p) else os.path.join(root, p))


def anchored_root(explicit_root=None):
    """Resolve + validate the MAIN worktree root. Returns (root, None) on success or
    (None, error_message) on a fail-closed refusal. See module docstring (FC68).

    Validation is pathname-INDEPENDENT. After canonicalizing the candidate with
    realpath (defeating symlink aliases and, on case-insensitive filesystems,
    case-variant spellings), Git itself decides whether it is the MAIN worktree:
      - `rev-parse --show-toplevel` must equal the candidate (it is a worktree ROOT,
        not a subdirectory), and
      - `--git-dir` must equal `--git-common-dir` (a LINKED worktree's per-worktree
        git-dir <main>/.git/worktrees/<name> differs from the shared common dir;
        the main worktree's are identical).
    So a linked worktree placed ANYWHERE -- not only under `.claude/worktrees/`,
    and reached via a symlink or a case variant -- is still rejected. An explicit
    --root MUST be absolute (a relative value would re-introduce the cwd coupling
    this whole fix removes)."""
    if explicit_root is not None:
        expanded = os.path.expanduser(explicit_root)
        if not os.path.isabs(expanded):
            return None, (f"--root must be an absolute path, got {explicit_root!r}")
        candidate = expanded
    else:
        # <repo>/.claude/hooks/firebreak-activate.py -> dirname x3 == <repo>
        candidate = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
    # Canonicalize BEFORE validation, sentinel placement, and repo_root storage.
    root = os.path.realpath(candidate)

    # (1) Must be a real firebreak repo. NECESSARY but not sufficient -- a linked
    # worktree also carries a tracked firebreak-classify.py; the git checks are the
    # teeth.
    classifier = os.path.join(root, ".claude", "hooks", "firebreak-classify.py")
    if not os.path.isfile(classifier):
        return None, (f"resolved root {root} has no "
                      ".claude/hooks/firebreak-classify.py (not a firebreak repo)")

    # (2) Must be a git working tree whose TOP-LEVEL is `root` itself, not a subdir
    # (a subdir would put the sentinel below the level workers walk up to).
    toplevel = _git(root, "rev-parse", "--show-toplevel")
    if toplevel is None:
        return None, (f"resolved root {root} is not a git working tree")
    if os.path.realpath(toplevel) != root:
        return None, (f"resolved root {root} is not a worktree top-level "
                      f"(git top-level is {os.path.realpath(toplevel)})")

    # (3) Must be the MAIN worktree, not a linked one -- pathname-independent.
    git_dir = _resolve_git_path(root, _git(root, "rev-parse", "--git-dir"))
    common_dir = _resolve_git_path(root, _git(root, "rev-parse", "--git-common-dir"))
    if git_dir is None or common_dir is None:
        return None, (f"resolved root {root}: could not read git metadata")
    if git_dir != common_dir:
        return None, (f"resolved root {root} is a LINKED worktree "
                      f"(git-dir {git_dir} != common-dir {common_dir}); the firebreak "
                      "sentinel must live at the MAIN worktree root")
    return root, None


def sentinel_path(root):
    return os.path.join(root, SENTINEL_REL)


def derive_project_key(root):
    # Mirror the auto-memory key shape: path with separators -> dashes.
    return root.replace(os.sep, "-").strip("-")


def activate(argv, root):
    if not argv:
        sys.stderr.write("activate: run_id required\n")
        return 2
    run_id = argv[0]
    project_key = argv[1] if len(argv) > 1 and argv[1] else derive_project_key(root)
    phase = argv[2] if len(argv) > 2 and argv[2] else "build"
    if len(argv) > 3 and argv[3]:
        try:
            test_allowlist = json.loads(argv[3])
        except Exception as e:
            sys.stderr.write(f"activate: bad test_allowlist JSON: {e}\n")
            return 2
    else:
        test_allowlist = dict(DEFAULT_TEST_ALLOWLIST)
    path = sentinel_path(root)
    # clear any stale sentinel from a crashed prior run, then write fresh.
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    record = {
        "run_id": run_id,
        "repo_root": root,
        "project_key": project_key,
        "phase": phase,
        "test_allowlist": test_allowlist,
    }
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(record, f, indent=2)
    os.rename(tmp, path)
    print(f"firebreak ACTIVE: run={run_id} phase={phase} root={root}")
    return 0


def set_phase(argv, root):
    if not argv:
        sys.stderr.write("set-phase: phase required\n")
        return 2
    path = sentinel_path(root)
    if not os.path.isfile(path):
        sys.stderr.write("set-phase: no active sentinel\n")
        return 1
    with open(path) as f:
        record = json.load(f)
    record["phase"] = argv[0]
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(record, f, indent=2)
    os.rename(tmp, path)
    print(f"firebreak phase -> {argv[0]}")
    return 0


def deactivate(_argv, root):
    path = sentinel_path(root)
    try:
        if os.path.exists(path):
            os.remove(path)
            print("firebreak INACTIVE (sentinel removed)")
        else:
            print("firebreak already inactive")
    except OSError as e:
        sys.stderr.write(f"deactivate: {e}\n")
        return 1
    return 0


def status(_argv, root):
    path = sentinel_path(root)
    if os.path.isfile(path):
        with open(path) as f:
            record = json.load(f)
        print(f"ACTIVE run={record.get('run_id')} phase={record.get('phase')} "
              f"root={record.get('repo_root')}")
    else:
        print("INACTIVE")
    return 0


CMDS = {"activate": activate, "set-phase": set_phase,
        "deactivate": deactivate, "status": status}


def _extract_root(argv):
    """Pull an optional `--root <abs>` / `--root=<abs>` out of argv (anywhere after
    the subcommand) so the existing positional shapes are unchanged. Returns
    (explicit_root, remaining_argv); explicit_root is None if absent or the literal
    "__MISSING__" if `--root` had no value."""
    root = None
    out = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--root":
            if i + 1 >= len(argv):
                return "__MISSING__", out
            root = argv[i + 1]
            i += 2
            continue
        if a.startswith("--root="):
            root = a.split("=", 1)[1]
            i += 1
            continue
        out.append(a)
        i += 1
    return root, out


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        sys.stderr.write(f"usage: {sys.argv[0]} "
                         "{activate|set-phase|deactivate|status} ... [--root <abs>]\n")
        return 2
    cmd = sys.argv[1]
    explicit_root, rest = _extract_root(sys.argv[2:])
    if explicit_root == "__MISSING__":
        sys.stderr.write("error: --root requires an absolute path value\n")
        return 2
    root, err = anchored_root(explicit_root)
    if err:
        sys.stderr.write(f"firebreak-activate: REFUSING ({cmd}): {err}\n")
        return 3
    return CMDS[cmd](rest, root)


if __name__ == "__main__":
    sys.exit(main())
