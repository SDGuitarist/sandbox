#!/usr/bin/env python3
"""Spike 0c fixture builder — per-wave swarm-runner reuse (plan §0.0c).

Creates, IN THE SANDBOX REPO, a throwaway base branch `spike-0c-base` (cut from
current HEAD) and two DISJOINT sets of COMPLETED worker branches:
  wave 1: swarm-SPIKE-w1-alpha, swarm-SPIKE-w1-beta   (own files under spikepkg_w1/)
  wave 2: swarm-SPIKE-w2-gamma, swarm-SPIKE-w2-delta  (own files under spikepkg_w2/)
Each worker branch carries ONE commit touching a uniquely-namespaced file, rooted
on `spike-0c-base` (so swarm-runner's merge-base == spike-0c-base HEAD and the
cherry-pick range is exactly the worker's commit).

It does NOT run swarm-runner — that is done by the orchestrator via the Agent tool,
TWICE (fresh context each), with:
  Invocation 1 (wave 1): original_branch=spike-0c-base,
      reports_dir=docs/reports/SPIKE/w1/, assembly_branch=swarm-SPIKE-w1-assembly,
      worker_branches=[swarm-SPIKE-w1-alpha, swarm-SPIKE-w1-beta]
  Invocation 2 (wave 2): original_branch=spike-0c-base,
      reports_dir=docs/reports/SPIKE/w2/, assembly_branch=swarm-SPIKE-w2-assembly,
      worker_branches=[swarm-SPIKE-w2-gamma, swarm-SPIKE-w2-delta]
(A minimal plan_path with a trivial spec/route list + test command is written to
docs/reports/SPIKE/spike-plan.md so swarm-runner's contract/smoke/test steps are
no-ops that PASS.)

PASS criteria (checked by tools/spike_per_wave_runner_check.py AFTER both runs):
- each run wrote its OWN w<k>/assembly-summary.md STATUS: PASS (report isolation);
- after run 2: `git branch --list 'swarm-SPIKE-*'` empty (both assembly branches
  gone) and no leftover spike worktrees;
- w2 summary references only w2 branches/bases (no cross-references to w1).

Cleanup: tools/spike_per_wave_runner_setup.py --teardown removes spike-0c-base,
all swarm-SPIKE-* branches/worktrees, and docs/reports/SPIKE/.

Run:  python3 tools/spike_per_wave_runner_setup.py            # build fixture
      python3 tools/spike_per_wave_runner_setup.py --teardown # remove fixture
"""

import os
import subprocess
import sys

REPO = "/Users/alejandroguillen/Projects/sandbox"
BASE = "spike-0c-base"
WORKERS = {
    "swarm-SPIKE-w1-alpha": ("spikepkg_w1/alpha.py", "def a():\n    return 'a'\n"),
    "swarm-SPIKE-w1-beta": ("spikepkg_w1/beta.py", "def b():\n    return 'b'\n"),
    "swarm-SPIKE-w2-gamma": ("spikepkg_w2/gamma.py", "def g():\n    return 'g'\n"),
    "swarm-SPIKE-w2-delta": ("spikepkg_w2/delta.py", "def d():\n    return 'd'\n"),
}
ENV = dict(os.environ, GIT_AUTHOR_NAME="spike", GIT_AUTHOR_EMAIL="spike@local",
           GIT_COMMITTER_NAME="spike", GIT_COMMITTER_EMAIL="spike@local")


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args], env=ENV,
                          capture_output=True, text=True)


def build():
    start = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    git("branch", "-f", BASE, "HEAD")
    for branch, (relpath, body) in WORKERS.items():
        git("branch", "-f", branch, BASE)
        wt = os.path.join(REPO, ".claude/worktrees", branch)
        git("worktree", "add", "-f", wt, branch)
        p = os.path.join(wt, relpath)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(body)
        subprocess.run(["git", "-C", wt, "add", "-A"], env=ENV, capture_output=True)
        subprocess.run(["git", "-C", wt, "commit", "-m", f"worker {branch}"],
                       env=ENV, capture_output=True)
    os.makedirs(os.path.join(REPO, "docs/reports/SPIKE"), exist_ok=True)
    with open(os.path.join(REPO, "docs/reports/SPIKE/spike-plan.md"), "w") as f:
        f.write("# Spike 0c plan\n\nNo routes. Test command: `true`.\n"
                "Contract: none. Smoke: none.\n")
    print(f"Fixture built (started on branch {start}). Base={BASE}.")
    print("Worker branches:", ", ".join(WORKERS))
    print("Now spawn swarm-runner TWICE (see this file's docstring for parameters).")


def teardown():
    for branch in list(WORKERS) + ["swarm-SPIKE-w1-assembly", "swarm-SPIKE-w2-assembly"]:
        wt = os.path.join(REPO, ".claude/worktrees", branch)
        git("worktree", "remove", "--force", wt)
        git("branch", "-D", branch)
    git("worktree", "prune")
    git("branch", "-D", BASE)
    subprocess.run(["rm", "-rf", os.path.join(REPO, "docs/reports/SPIKE")],
                   capture_output=True)
    print("Fixture torn down (spike-0c-base, swarm-SPIKE-* branches/worktrees, docs/reports/SPIKE).")


if __name__ == "__main__":
    if "--teardown" in sys.argv:
        teardown()
    else:
        build()
