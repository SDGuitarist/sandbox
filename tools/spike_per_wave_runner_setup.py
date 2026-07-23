#!/usr/bin/env python3
"""Spike 0c fixture builder — per-wave swarm-runner reuse (plan §0.0c, rev5).

REV5 RESHAPE (Codex Finding 4). The prior fixture cut a synthetic `spike-0c-base`
from current HEAD and used `original_branch=spike-0c-base`, so
`merge-base(original_branch, worker) == original_branch HEAD` — the base-divergence
that swarm-runner Step 3 exists to handle was NOT exercised. This version builds
the REAL `origin/<default>` / `original_branch` ancestry shape:

  spike-default            — the DEFAULT branch (origin/<default> analog); pushed to
                             a local bare remote `spikeorigin` so
                             `spikeorigin/spike-default` is a real remote-tracking
                             ref (baseRef=fresh). Workers root HERE.
  spike-feat               — the FEATURE branch (original_branch), AHEAD of
                             spike-default by 1 commit (a namespaced feature file).
  swarm-SPIKE-w1-alpha/beta, swarm-SPIKE-w2-gamma/delta
                           — two disjoint COMPLETED worker sets, each rooted on
                             spike-default tip, one commit on a uniquely-namespaced
                             file. So merge-base(spike-feat, worker) == spike-default
                             tip != spike-feat HEAD (genuine base-divergence; the
                             feature commit is never in a worker's cherry-pick range).

swarm-runner is then spawned TWICE (fresh context each) with original_branch=spike-feat
and the two worker sets (see this file's docstring / plan §0.0c for parameters).
Adjudicated by tools/spike_per_wave_runner_check.py.

The real GitHub `origin` remote is NEVER touched; the bare repo is added under a
DISTINCT remote name `spikeorigin` and lives in a temp dir recorded in
docs/reports/SPIKE/fixture-state.json for teardown.

Run:  python3 tools/spike_per_wave_runner_setup.py            # build fixture
      python3 tools/spike_per_wave_runner_setup.py --teardown # remove fixture
"""

import json
import os
import subprocess
import sys
import tempfile

REPO = "/Users/alejandroguillen/Projects/sandbox"
DEFAULT = "spike-default"
FEAT = "spike-feat"
REMOTE = "spikeorigin"
SPIKE_DIR = os.path.join(REPO, "docs/reports/SPIKE")
STATE = os.path.join(SPIKE_DIR, "fixture-state.json")
WT_ROOT = os.path.join(REPO, ".claude/worktrees")

WORKERS_W1 = {
    "swarm-SPIKE-w1-alpha": ("spikepkg_w1/alpha.py", "def a():\n    return 'a'\n"),
    "swarm-SPIKE-w1-beta": ("spikepkg_w1/beta.py", "def b():\n    return 'b'\n"),
}
WORKERS_W2 = {
    "swarm-SPIKE-w2-gamma": ("spikepkg_w2/gamma.py", "def g():\n    return 'g'\n"),
    "swarm-SPIKE-w2-delta": ("spikepkg_w2/delta.py", "def d():\n    return 'd'\n"),
}
ALL_WORKERS = {**WORKERS_W1, **WORKERS_W2}
ASSEMBLY_BRANCHES = ["swarm-SPIKE-w1-assembly", "swarm-SPIKE-w2-assembly"]

ENV = dict(os.environ, GIT_AUTHOR_NAME="spike", GIT_AUTHOR_EMAIL="spike@local",
           GIT_COMMITTER_NAME="spike", GIT_COMMITTER_EMAIL="spike@local")

BUILD_TRACKING = """\
# BUILD_TRACKING — SPIKE 0c (throwaway)

## AGENT_STATUS

| # | Role | Commit | Status |
|---|------|--------|--------|
---

## Phase Status

| Phase | Status | Report |
|-------|--------|--------|
---

## Run State

- final_status: IN_PROGRESS
"""

SPIKE_PLAN = """\
# Spike 0c plan (throwaway)

This plan drives swarm-runner's contract/smoke/test steps to trivial PASSes so the
spike measures ONLY assembly + cleanup + report isolation + base-divergence.

- Prescribed routes: NONE (smoke test has nothing to curl -> PASS/skip).
- Test command: `true` (exit 0 -> test suite PASS).
- Export names / cross-boundary wiring: NONE. Each worker writes a disjoint,
  uniquely-namespaced file (spikepkg_w1/*, spikepkg_w2/*); the contract grep has no
  prescribed names to find -> vacuously PASS.
"""


def git(*args, cwd=REPO):
    return subprocess.run(["git", "-C", cwd, *args], env=ENV,
                          capture_output=True, text=True)


def _write(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(body)


def _commit_file_on_branch(branch, base, relpath, body, msg):
    """Create `branch` at `base`, add one commit touching `relpath`, in a temp
    worktree; return (worktree_path, head_sha). Caller decides whether to keep or
    remove the worktree."""
    git("branch", "-f", branch, base)
    wt = os.path.join(WT_ROOT, branch)
    git("worktree", "add", "-f", wt, branch)
    _write(os.path.join(wt, relpath), body)
    git("add", "-A", cwd=wt)
    git("commit", "-m", msg, cwd=wt)
    head = git("rev-parse", branch).stdout.strip()
    return wt, head


def build():
    start = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    # --- DEFAULT branch (origin/<default> analog) at current HEAD ---
    git("branch", "-f", DEFAULT, "HEAD")
    default_tip = git("rev-parse", DEFAULT).stdout.strip()

    # --- Local bare remote `spikeorigin` so spikeorigin/spike-default is real ---
    origin_path = tempfile.mkdtemp(prefix="spike0c-origin-")
    subprocess.run(["git", "init", "--bare", origin_path], env=ENV,
                   capture_output=True, text=True)
    git("remote", "remove", REMOTE)  # tolerate a stale remote
    git("remote", "add", REMOTE, origin_path)
    git("push", REMOTE, f"{DEFAULT}:{DEFAULT}")
    git("fetch", REMOTE)

    # --- FEATURE branch AHEAD of default by 1 commit (built in a temp worktree,
    #     then the worktree is REMOVED so swarm-runner can `git checkout spike-feat`
    #     in the main worktree) ---
    feat_wt, feat_head = _commit_file_on_branch(
        FEAT, DEFAULT, "spikefeat/feature.py",
        "def feature():\n    return 'feat'\n", "feat: ahead-of-default marker")
    git("worktree", "remove", "--force", feat_wt)

    # --- Worker branches rooted on spike-default tip (NOT spike-feat) ---
    worker_heads = {}
    for branch, (relpath, body) in ALL_WORKERS.items():
        _, head = _commit_file_on_branch(branch, DEFAULT, relpath, body,
                                         f"worker {branch}")
        worker_heads[branch] = head

    # --- Throwaway plan + BUILD_TRACKING for swarm-runner ---
    _write(os.path.join(SPIKE_DIR, "spike-plan.md"), SPIKE_PLAN)
    _write(os.path.join(SPIKE_DIR, "BUILD_TRACKING.md"), BUILD_TRACKING)
    _write(STATE, json.dumps({
        "start_branch": start,
        "default_branch": DEFAULT,
        "feat_branch": FEAT,
        "remote": REMOTE,
        "origin_path": origin_path,
        "default_tip": default_tip,
        "feat_head": feat_head,
        "worker_heads": worker_heads,
        "wave1": list(WORKERS_W1),
        "wave2": list(WORKERS_W2),
    }, indent=2) + "\n")

    print(f"Fixture built (started on branch {start}).")
    print(f"  {DEFAULT} tip     = {default_tip}  (workers root here; == {REMOTE}/{DEFAULT})")
    print(f"  {FEAT} head       = {feat_head}  (ahead of {DEFAULT} by 1)")
    print(f"  bare remote       = {origin_path}")
    print("Wave-1 workers:", ", ".join(WORKERS_W1))
    print("Wave-2 workers:", ", ".join(WORKERS_W2))
    print("Now spawn swarm-runner TWICE with original_branch=spike-feat (see docstring).")


def teardown():
    # Restore the original branch first (swarm-runner leaves HEAD on spike-feat).
    start = None
    if os.path.exists(STATE):
        try:
            start = json.load(open(STATE)).get("start_branch")
        except Exception:
            start = None
    if start:
        git("checkout", "--force", start)

    for branch in list(ALL_WORKERS) + ASSEMBLY_BRANCHES:
        wt = os.path.join(WT_ROOT, branch)
        git("worktree", "remove", "--force", wt)
        git("branch", "-D", branch)
    git("worktree", "prune")
    git("branch", "-D", FEAT)
    git("branch", "-D", DEFAULT)

    origin_path = None
    if os.path.exists(STATE):
        try:
            origin_path = json.load(open(STATE)).get("origin_path")
        except Exception:
            origin_path = None
    git("remote", "remove", REMOTE)
    if origin_path and os.path.isdir(origin_path):
        subprocess.run(["rm", "-rf", origin_path], capture_output=True)
    subprocess.run(["rm", "-rf", SPIKE_DIR], capture_output=True)
    print(f"Fixture torn down ({DEFAULT}, {FEAT}, swarm-SPIKE-* branches/worktrees, "
          f"remote {REMOTE} + bare repo, docs/reports/SPIKE).")


if __name__ == "__main__":
    if "--teardown" in sys.argv:
        teardown()
    else:
        build()
