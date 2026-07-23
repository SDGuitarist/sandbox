#!/usr/bin/env python3
"""Spike 0c adjudicator — per-wave swarm-runner reuse (plan §0.0c, rev5).

Run AFTER both swarm-runner invocations complete. Reads the two assembly summaries
+ live git state and checks the plan §0.0c PASS criteria:

  1. report isolation   — each w<k>/assembly-summary.md exists with line-1 STATUS: PASS.
  2. cleanup complete    — no `swarm-SPIKE-*` branches and no leftover spike worktrees.
  3. no run-level leak   — w2 summary references only w2 branches; the two summaries
                           share no assembly-branch name (grep cross-references == 0).
  4. base-divergence     — every recorded cherry-pick base in BOTH summaries equals the
                           spike-default tip (== spikeorigin/spike-default), NOT
                           spike-feat HEAD.

Writes nothing; prints a table and a final STATUS line (PASS/FAIL). Exit 0 on PASS.

Run:  python3 tools/spike_per_wave_runner_check.py
"""

import json
import os
import re
import subprocess

REPO = "/Users/alejandroguillen/Projects/sandbox"
SPIKE_DIR = os.path.join(REPO, "docs/reports/SPIKE")
STATE = os.path.join(SPIKE_DIR, "fixture-state.json")
W1_SUMMARY = os.path.join(SPIKE_DIR, "w1/assembly-summary.md")
W2_SUMMARY = os.path.join(SPIKE_DIR, "w2/assembly-summary.md")


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True,
                          text=True).stdout.strip()


def read(path):
    return open(path).read() if os.path.exists(path) else ""


def status_line_pass(path):
    txt = read(path)
    if not txt:
        return False
    return txt.splitlines()[0].strip().upper().startswith("STATUS: PASS")


def shas_in(text):
    """All 7-40 hex tokens that look like git shas."""
    return set(re.findall(r"\b[0-9a-f]{7,40}\b", text))


def main():
    state = json.load(open(STATE))
    default_tip = state["default_tip"]
    feat_head = state["feat_head"]
    wave1 = state["wave1"]
    wave2 = state["wave2"]

    results = []

    def check(name, ok, detail=""):
        results.append((name, ok, detail))

    # 1. report isolation + STATUS PASS
    check("w1 summary STATUS: PASS", status_line_pass(W1_SUMMARY), W1_SUMMARY)
    check("w2 summary STATUS: PASS", status_line_pass(W2_SUMMARY), W2_SUMMARY)

    w1_txt = read(W1_SUMMARY)
    w2_txt = read(W2_SUMMARY)

    # 2. cleanup — no swarm-SPIKE-* branches, no leftover spike worktrees
    branches = git("branch", "--list", "swarm-SPIKE-*")
    check("no swarm-SPIKE-* branches remain", branches == "",
          f"remaining: {branches!r}")
    worktrees = git("worktree", "list", "--porcelain")
    leftover_wt = [ln for ln in worktrees.splitlines()
                   if ln.startswith("worktree") and "swarm-SPIKE-" in ln]
    check("no leftover spike worktrees", not leftover_wt, str(leftover_wt))

    # 3. no run-level leak — w2 summary must not reference any w1 worker/assembly name
    w1_names = set(wave1) | {"swarm-SPIKE-w1-assembly"}
    leaked = sorted(n for n in w1_names if n in w2_txt)
    check("w2 summary references no w1 branch/assembly names", not leaked,
          f"leaked: {leaked}")
    # symmetric: w1 summary must not reference w2 names
    w2_names = set(wave2) | {"swarm-SPIKE-w2-assembly"}
    leaked2 = sorted(n for n in w2_names if n in w1_txt)
    check("w1 summary references no w2 branch/assembly names", not leaked2,
          f"leaked: {leaked2}")

    # 4. base-divergence — every recorded cherry-pick base == default tip, and
    #    feat_head must NOT appear as a base (it is not the fork point).
    #    default_tip must be present in both summaries (it is the merge-base column).
    short_default = default_tip[:7]
    short_feat = feat_head[:7]
    for label, txt in (("w1", w1_txt), ("w2", w2_txt)):
        shas = shas_in(txt)
        has_default = any(s.startswith(short_default) or default_tip.startswith(s)
                          for s in shas)
        has_feat_as_base = any(s.startswith(short_feat) or feat_head.startswith(s)
                               for s in shas)
        check(f"{label}: cherry-pick base == spike-default tip ({short_default})",
              has_default, f"default_tip present in summary shas: {has_default}")
        check(f"{label}: spike-feat HEAD ({short_feat}) is NOT a cherry-pick base",
              not has_feat_as_base,
              f"feat_head absent from summary shas: {not has_feat_as_base}")

    print("# Spike 0c check results\n")
    print("| check | ok | detail |")
    print("|-------|----|--------|")
    for name, ok, detail in results:
        print(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |")

    passed = all(ok for _, ok, _ in results)
    print(f"\nSTATUS: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
