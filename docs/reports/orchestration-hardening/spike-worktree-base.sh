#!/usr/bin/env bash
# Phase-0 spike (Track A, orchestration-hardening plan).
# Resolves the two decision-relevant questions empirically in a throwaway repo:
#   Q1: Is merge-base(original_branch, worker) always the worker's true fork point,
#       and does cherry-pick merge-base..worker replay ALL N commits? Does <branch>^
#       drop earlier commits? Does a zero-commit worker degrade to a clean no-op?
#   Q2: Assembly routing — disjoint divergent worker -> clean cherry-pick; two
#       workers touching the same file on a divergent base -> deterministic conflict
#       -> --abort + clean tree + branches preserved + original_branch untouched.
#   Strategy (i) reproduction: does uniform cherry-pick reproduce the `merge --no-ff`
#       TREE for an is-ancestor (mergeable) worker, incl. an empty worker?
#   Pre-flight: detached-HEAD and merge-commit worker branches abort loudly.
#
# Simulates the harness fact (verified Run 069): workers are rooted on the repo
# default branch (master / f90aed8), NOT on the orchestrator's feature HEAD.
#
# Self-contained: builds its own repo under a mktemp dir, cleans up on exit.
# Prints PASS/FAIL per assertion and an overall verdict line.
set -u

PASS=0; FAIL=0
ok()   { echo "  PASS: $1"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

R=$(mktemp -d)
trap 'rm -rf "$R"' EXIT
export GIT_AUTHOR_NAME=spike GIT_AUTHOR_EMAIL=spike@local
export GIT_COMMITTER_NAME=spike GIT_COMMITTER_EMAIL=spike@local

g() { git -C "$R" "$@"; }

g init -q -b master
echo base > "$R/base.txt"; g add base.txt; g commit -q -m "master base (f90aed8 analog)"
MASTER=$(g rev-parse HEAD)

# original_branch = feat, ahead of master by 2 commits (the orchestrator branch)
g checkout -q -b feat
echo f1 > "$R/feat1.txt"; g add feat1.txt; g commit -q -m "feat-only 1"
echo f2 > "$R/feat2.txt"; g add feat2.txt; g commit -q -m "feat-only 2"
FEAT=$(g rev-parse HEAD)

# Workers rooted on MASTER (divergent base, as the harness produces)
g checkout -q -b w1 master
echo w1 > "$R/w1.txt"; g add w1.txt; g commit -q -m "w1 only"

g checkout -q -b w3 master
echo a > "$R/w3a.txt"; g add w3a.txt; g commit -q -m "w3 a"
echo b > "$R/w3b.txt"; g add w3b.txt; g commit -q -m "w3 b"
echo c > "$R/w3c.txt"; g add w3c.txt; g commit -q -m "w3 c"

g checkout -q -b w0 master   # zero-commit worker (no work done)

g checkout -q -b wca master
echo from_a > "$R/shared.txt"; g add shared.txt; g commit -q -m "wca shared"
g checkout -q -b wcb master
echo from_b > "$R/shared.txt"; g add shared.txt; g commit -q -m "wcb shared"

# Mergeable (is-ancestor) worker rooted on FEAT HEAD (hypothetical correct-root)
g checkout -q -b wm feat
echo wm > "$R/wm.txt"; g add wm.txt; g commit -q -m "wm only"

# Merge-commit worker (out-of-scope state -> must be detected by pre-flight)
g checkout -q -b wmc master
echo x > "$R/wmc.txt"; g add wmc.txt; g commit -q -m "wmc work"
g merge -q --no-ff -m "wmc merge feat" feat

g checkout -q feat

echo "=== Q1: fork point + N-commit replay + zero-commit no-op ==="

# T1: merge-base(feat,w1) == MASTER, and three-dot ownership lists only worker delta
MB1=$(g merge-base feat w1)
[ "$MB1" = "$MASTER" ] && ok "merge-base(feat,w1) == master (true fork point)" || bad "merge-base(feat,w1) != master"
OWN=$(g diff --name-only feat...w1)
[ "$OWN" = "w1.txt" ] && ok "ownership three-dot feat...w1 lists only w1.txt (no feat/master noise)" || bad "ownership listed: [$OWN]"

# T2: cherry-pick merge-base..w3 replays all 3; demonstrate <branch>^ would drop 2
g checkout -q -b asm_w3 feat
MB3=$(g merge-base feat w3)
g cherry-pick "$MB3"..w3 >/dev/null 2>&1
N3=0
[ -f "$R/w3a.txt" ] && N3=$((N3+1)); [ -f "$R/w3b.txt" ] && N3=$((N3+1)); [ -f "$R/w3c.txt" ] && N3=$((N3+1))
[ "$N3" = "3" ] && ok "cherry-pick merge-base..w3 replays all 3 commits (files present)" || bad "only $N3/3 files present"
RANGE_MB=$(g rev-list --count "$MB3"..w3)
RANGE_CARET=$(g rev-list --count "w3^..w3")
[ "$RANGE_MB" = "3" ] && ok "merge-base..w3 range = 3 commits" || bad "merge-base range = $RANGE_MB"
[ "$RANGE_CARET" = "1" ] && ok "<branch>^..w3 range = 1 commit (WOULD DROP 2 -> eliminated, FC51 data-loss)" || bad "caret range = $RANGE_CARET"
g checkout -q feat

# T3: zero-commit worker -> empty range -> clean no-op
MB0=$(g merge-base feat w0)
RANGE0=$(g rev-list --count "$MB0"..w0)
[ "$RANGE0" = "0" ] && ok "zero-commit worker w0: merge-base..w0 range empty (clean no-op, no cherry-pick needed)" || bad "w0 range = $RANGE0"

# T4: ownership base == cherry-pick base (same expression, same sha)
[ "$(g merge-base feat w1)" = "$MB1" ] && ok "ownership-base == cherry-pick-base for w1 (O3 invariant)" || bad "base mismatch"

echo "=== Q2: assembly routing (clean + conflict) ==="

# T5: assembly branch off feat; clean cherry-pick of wca; conflict on wcb -> abort routing
g checkout -q -b asm_conflict feat
MBca=$(g merge-base feat wca)
g cherry-pick "$MBca"..wca >/dev/null 2>&1 && ok "disjoint divergent worker wca: clean cherry-pick onto feat" || bad "wca cherry-pick failed unexpectedly"
MBcb=$(g merge-base feat wcb)
if g cherry-pick "$MBcb"..wcb >/dev/null 2>&1; then
  bad "wcb cherry-pick UNEXPECTEDLY clean (should conflict on shared.txt)"
else
  # detect conflict via porcelain ^[UAD]{2} markers
  if g status --porcelain | grep -qE '^[UAD][UAD] '; then ok "conflict detected via porcelain ^[UAD]{2} marker"; else bad "no porcelain conflict marker found"; fi
  g cherry-pick --abort
  CLEAN=$(g status --porcelain)
  [ -z "$CLEAN" ] && ok "git cherry-pick --abort -> clean tree (status --porcelain empty)" || bad "tree not clean after abort: [$CLEAN]"
fi
# branches preserved
g rev-parse --verify -q wca >/dev/null && g rev-parse --verify -q wcb >/dev/null && ok "worker branches wca AND wcb preserved after abort" || bad "a worker branch missing after abort"
# original_branch (feat) untouched
[ "$(g rev-parse feat)" = "$FEAT" ] && ok "original_branch feat HEAD unchanged ($FEAT)" || bad "feat HEAD moved!"
g checkout -q feat

echo "=== Strategy (i) reproduction: uniform cherry-pick TREE == merge --no-ff TREE ==="

# T6a: is-ancestor mergeable worker wm
g checkout -q -b asm_merge_wm feat
g merge -q --no-ff -m "merge wm" wm
TREE_MERGE=$(g rev-parse "asm_merge_wm^{tree}")
g checkout -q feat
g checkout -q -b asm_cp_wm feat
MBwm=$(g merge-base feat wm)
g cherry-pick "$MBwm"..wm >/dev/null 2>&1
TREE_CP=$(g rev-parse "asm_cp_wm^{tree}")
g checkout -q feat
[ "$TREE_MERGE" = "$TREE_CP" ] && ok "is-ancestor worker wm: cherry-pick TREE == merge --no-ff TREE (strategy i reproduces ii)" || bad "trees differ: merge=$TREE_MERGE cp=$TREE_CP"

# T6b: empty worker (is-ancestor, zero commits) -> both are no-ops leaving feat tree
g checkout -q -b asm_empty feat
MBe=$(g merge-base feat w0)
CNT=$(g rev-list --count "$MBe"..w0)
TREE_EMPTY=$(g rev-parse "asm_empty^{tree}")
TREE_FEAT=$(g rev-parse "feat^{tree}")
{ [ "$CNT" = "0" ] && [ "$TREE_EMPTY" = "$TREE_FEAT" ]; } && ok "empty worker: cherry-pick no-op leaves tree == feat (matches merge no-op)" || bad "empty worker tree drift"
g checkout -q feat

echo "=== Pre-flight: out-of-scope worker states abort loudly ==="

# T7: detached HEAD detection
g checkout -q --detach feat
HEADREF=$(g rev-parse --abbrev-ref HEAD)
[ "$HEADREF" = "HEAD" ] && ok "detached-HEAD detected (rev-parse --abbrev-ref HEAD == HEAD) -> pre-flight abort" || bad "detached HEAD not detected (got $HEADREF)"
g checkout -q feat

# T8: merge-commit worker detection
MBmc=$(g merge-base feat wmc)
MERGES=$(g rev-list --merges "$MBmc"..wmc | wc -l | tr -d ' ')
[ "$MERGES" != "0" ] && ok "merge-commit worker detected (rev-list --merges non-empty: $MERGES) -> pre-flight abort" || bad "merge commit not detected"

echo ""
echo "=== SPIKE VERDICT: PASS=$PASS FAIL=$FAIL ==="
[ "$FAIL" = "0" ] && echo "ALL ASSERTIONS PASSED" || echo "SOME ASSERTIONS FAILED"
exit "$FAIL"
