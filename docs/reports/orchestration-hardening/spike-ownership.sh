#!/usr/bin/env bash
# Focused spike: the three-dot ownership gate on a worker rooted on a STALE base
# (master), with original_branch (feat) ahead. Asserts the gate attributes ONLY
# the worker's fork-point delta -- no feat/master noise. Backs the Track A
# one-token fix (main -> original_branch) at SKILL.md ownership gate.
set -u
R=$(mktemp -d); trap 'rm -rf "$R"' EXIT
export GIT_AUTHOR_NAME=spike GIT_AUTHOR_EMAIL=spike@local GIT_COMMITTER_NAME=spike GIT_COMMITTER_EMAIL=spike@local
g() { git -C "$R" "$@"; }

g init -q -b master
echo base > "$R/base.txt"; g add base.txt; g commit -q -m base
g checkout -q -b feat
echo f > "$R/feat_only.txt"; g add feat_only.txt; g commit -q -m "feat ahead of master"
g checkout -q -b worker master   # harness roots worker on master, not feat
echo w > "$R/worker_file.txt"; g add worker_file.txt; g commit -q -m "worker work"

OWN=$(g diff --name-only feat...worker)
echo "ownership (feat...worker): [$OWN]"
if [ "$OWN" = "worker_file.txt" ]; then
  echo "PASS: stale-based worker lists only its own file (no feat_only.txt, no base.txt)"
  exit 0
else
  echo "FAIL: expected 'worker_file.txt', got '$OWN'"
  exit 1
fi
