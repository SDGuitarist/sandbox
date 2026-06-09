#!/usr/bin/env bash
# Focused spike: assembly conflict routing. Two workers touch the SAME file on a
# divergent base -> the second cherry-pick conflicts -> the path MUST NOT invoke
# inline spec resolution (that would mask an ownership-gate escape); instead
# `git cherry-pick --abort`, leave a CLEAN tree, PRESERVE worker branches, leave
# original_branch (feat) UNTOUCHED, and record `assembly-ownership-conflict:`.
set -u
R=$(mktemp -d); trap 'rm -rf "$R"' EXIT
export GIT_AUTHOR_NAME=spike GIT_AUTHOR_EMAIL=spike@local GIT_COMMITTER_NAME=spike GIT_COMMITTER_EMAIL=spike@local
g() { git -C "$R" "$@"; }
fail=0

g init -q -b master
echo base > "$R/base.txt"; g add base.txt; g commit -q -m base
g checkout -q -b feat
echo f > "$R/feat_only.txt"; g add feat_only.txt; g commit -q -m "feat ahead"
FEAT=$(g rev-parse feat)
g checkout -q -b wA master; echo A > "$R/shared.txt"; g add shared.txt; g commit -q -m wA
g checkout -q -b wB master; echo B > "$R/shared.txt"; g add shared.txt; g commit -q -m wB

g checkout -q -b assembly feat
g cherry-pick "$(g merge-base feat wA)"..wA >/dev/null 2>&1 || { echo "FAIL: wA should apply clean"; fail=1; }
if g cherry-pick "$(g merge-base feat wB)"..wB >/dev/null 2>&1; then
  echo "FAIL: wB should have conflicted on shared.txt"; fail=1
else
  g status --porcelain | grep -qE '^[UAD][UAD] ' && echo "PASS: conflict surfaced (porcelain ^[UAD]{2})" || { echo "FAIL: no conflict marker"; fail=1; }
  echo "ACTION: record blocking class -> assembly-ownership-conflict:"
  g cherry-pick --abort
fi

[ -z "$(g status --porcelain)" ] && echo "PASS: clean tree after --abort" || { echo "FAIL: tree dirty after abort"; fail=1; }
g rev-parse --verify -q wA >/dev/null && g rev-parse --verify -q wB >/dev/null && echo "PASS: worker branches preserved" || { echo "FAIL: a worker branch missing"; fail=1; }
[ "$(g rev-parse feat)" = "$FEAT" ] && echo "PASS: original_branch (feat) untouched" || { echo "FAIL: feat moved"; fail=1; }

[ "$fail" = "0" ] && echo "OVERALL: PASS" || echo "OVERALL: FAIL"
exit "$fail"
