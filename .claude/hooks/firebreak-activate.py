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
     carry their own tracked copy).
  2. __file__ anchor: this file lives at <repo>/.claude/hooks/, so the repo root is
     two directory levels up from the hooks dir.
The resolved root is VALIDATED and the tool FAILS CLOSED (loud stderr + non-zero
exit, NO sentinel written) when the root is inside a worktree or is not a real
firebreak repo -- converting the old silent wrong-root write into a hard refuse.

Exit 0 on success; 2 usage error; 3 fail-closed root refusal; 1 operational error.
"""
import json
import os
import sys

SENTINEL_REL = os.path.join(".claude", "firebreak-active.json")
DEFAULT_TEST_ALLOWLIST = {"pytest": True}


def anchored_root(explicit_root=None):
    """Resolve + validate the MAIN repo root. Returns (root, None) on success or
    (None, error_message) on a fail-closed refusal. See module docstring (FC68)."""
    if explicit_root:
        root = os.path.abspath(os.path.expanduser(explicit_root))
    else:
        # <repo>/.claude/hooks/firebreak-activate.py -> dirname x3 == <repo>
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
    norm = root.replace("\\", "/").rstrip("/") + "/"
    # (1) Refuse a root inside a worktree -- the sentinel must live at the MAIN root.
    # A worktree-local sentinel is invisible to SIBLING-wave workers (they walk up
    # from their OWN worktree and never traverse a sibling's), i.e. fail-open. This
    # is the load-bearing guard against the worktree's own tracked copy of this
    # script resolving __file__ to a worktree root.
    if "/.claude/worktrees/" in norm:
        return None, (f"resolved root is inside a worktree ({root}); "
                      "pass --root <main-repo-abs-path>")
    # (2) Refuse a root that is not a real firebreak repo (defends a bad --root and
    # a mis-anchored __file__).
    classifier = os.path.join(root, ".claude", "hooks", "firebreak-classify.py")
    if not os.path.isfile(classifier):
        return None, (f"resolved root {root} has no "
                      ".claude/hooks/firebreak-classify.py (not a firebreak repo); "
                      "pass --root <main-repo-abs-path>")
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
