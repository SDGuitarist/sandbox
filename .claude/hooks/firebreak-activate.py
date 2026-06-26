#!/usr/bin/env python3
"""G1 firebreak -- sentinel lifecycle (orchestrator-only, deterministic).

The PreToolUse classifier is a NO-OP unless `<repo_root>/.claude/firebreak-active.json`
exists (manual sessions untouched). The autopilot orchestrator calls this to write
that sentinel after the pre-spawn provenance gate / before worker spawn, flip its
phase before the tail-runner spawn, and remove it at run end.

Usage (always ONE command, never `python3 -c`):
  firebreak-activate.py activate <run_id> [project_key] [phase] [test_allowlist_json]
  firebreak-activate.py set-phase <phase>
  firebreak-activate.py deactivate
  firebreak-activate.py status

`activate` clears any stale sentinel first (a crashed prior run can leave one),
then writes a fresh record at the repo root (git toplevel, else cwd).
Exit 0 on success; non-zero + stderr on error.
"""
import json
import os
import subprocess
import sys

SENTINEL_REL = os.path.join(".claude", "firebreak-active.json")
DEFAULT_TEST_ALLOWLIST = {"pytest": True}


def repo_root():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return os.getcwd()


def sentinel_path():
    return os.path.join(repo_root(), SENTINEL_REL)


def derive_project_key(root):
    # Mirror the auto-memory key shape: path with separators -> dashes.
    return root.replace(os.sep, "-").strip("-")


def activate(argv):
    if not argv:
        sys.stderr.write("activate: run_id required\n")
        return 2
    run_id = argv[0]
    root = repo_root()
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
    path = os.path.join(root, SENTINEL_REL)
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


def set_phase(argv):
    if not argv:
        sys.stderr.write("set-phase: phase required\n")
        return 2
    path = sentinel_path()
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


def deactivate(_argv):
    path = sentinel_path()
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


def status(_argv):
    path = sentinel_path()
    if os.path.isfile(path):
        with open(path) as f:
            record = json.load(f)
        print(f"ACTIVE run={record.get('run_id')} phase={record.get('phase')}")
    else:
        print("INACTIVE")
    return 0


CMDS = {"activate": activate, "set-phase": set_phase,
        "deactivate": deactivate, "status": status}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        sys.stderr.write(f"usage: {sys.argv[0]} {{activate|set-phase|deactivate|status}} ...\n")
        return 2
    return CMDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
