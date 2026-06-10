# Codex Design Handoff — Track A P-extract (cherry-pick assembly → shared "do-it" tool)

**Type:** Architecture/design decision (advisory, pre-code). We have NOT written any
tool or fixture yet — we want your design call first.
**Date:** 2026-06-09
**Repo:** `~/Projects/sandbox` (Sandbox autopilot harness)
**Branch:** `feat/track-a-pextract-cherrypick` (off `master` @ `52ae069`)
**Decider:** Alejandro (beginner dev) + Claude Code, with Codex's recommendation.

---

## Read first (in order)

1. `HANDOFF.md` — current repo state.
2. `.claude/agents/swarm-runner.md` — **Step 3, lines 76–138** (the cherry-pick
   assembly prose we want to extract) + Steps 1–2 (the caller's branch setup) and
   Step 10.5w context (ownership gate / O3 invariant).
3. `tools/check_spec_provenance.py` — the **share-not-fork PRECEDENT** (a shipped,
   fixtured, single-purpose CLI the skill CALLS). Note: it is **read-only**; our new
   tool **mutates git state** — that difference is the crux.
4. `eval-harness/validate_hardening.py` + `eval-harness/fixtures/` + `fixtures/README.md`
   — the fixture suite this extraction must add a real `EXERCISED` row to (F-A1).
5. `docs/solutions/2026-06-09-orchestration-hardening-fixture-suite.md` — the honesty
   vocabulary (EXERCISED / SPIKE-VALIDATED / PROSE-ASSERTED / MIRRORED) and the
   "share-not-fork, never a Python mirror" principle.
6. `docs/reports/orchestration-hardening/spike-worktree-base.md` — proves worker
   worktrees root on the default branch, NOT the feature branch (why cherry-pick).

---

## The decision already made (don't re-litigate unless you see a blocker)

- We are upgrading **Track A (FC51 cherry-pick assembly)** from `P-accept` (agent-prose,
  field-proven) to **`P-extract`**: pull the per-worker assembly logic into a shared
  callable that BOTH `swarm-runner.md` Step 3 calls AND the fixture suite exercises
  (one implementation — share-not-fork).
- We chose the **"do-it" tool** shape (it performs the cherry-pick) over a
  "compute-only" planner, **specifically so the load-bearing range command
  (`git cherry-pick <base>..<branch>`) is under test** — the `<branch>^` form is the
  FC51 data-loss class and must never silently regress in prose.

**If you think do-it is wrong, say so** — but the rationale is "get the dangerous
command under test," which compute-only does not achieve.

---

## What Step 3 does today (the prose to extract), condensed

Per COMPLETED worker branch, as separate git commands:
1. **Fork-point base:** `git merge-base <original_branch> <branch>` → `base`
   (the O3 invariant — same base the ownership gate used).
2. **Pre-flight abort:** `git rev-list --merges <base>..<branch>` non-empty (a merge
   commit on the worker branch) → ownership-conflict abort. Detached-HEAD is
   **explicitly out of scope** (you get branch names, not worktree paths; falls
   through to the zero-commit no-op).
3. **Zero-commit no-op:** `git rev-list --count <base>..<branch>` == 0 → skip, note
   "empty delta", NOT an error.
4. **Cherry-pick full range:** `git cherry-pick <base>..<branch>` (replays ALL N
   commits; `<branch>^` is FORBIDDEN — silent multi-commit data loss).
5. **Conflict OR pre-flight abort = ownership-gate ESCAPE:** `git cherry-pick --abort`
   (if in progress), do NOT resolve inline, PRESERVE all worker branches, do NOT merge
   to `original_branch`, write `assembly-ownership-conflict.md`, set
   `final_status: FAIL`, return `STATUS: FAIL -- assembly-ownership-conflict: <branch>`.

On success: capture `git log -1 --format=%h`, append a BUILD_TRACKING AGENT_STATUS
row, record the per-worker base for the assembly summary.

---

## Proposed boundary (please confirm or correct)

**Tool = single-worker primitive.** `tools/assemble_worker.py
--original-branch <b> --worker-branch <w>` (names TBD). It:
- computes base, runs the merge-commit pre-flight, classifies the delta,
- on a clean non-empty delta runs `git cherry-pick <base>..<branch>`,
- on conflict runs `git cherry-pick --abort` and returns a CONFLICT status,
- emits a line-1 `STATUS:` + exit code (mirroring `check_spec_provenance.py`'s
  convention), e.g.:
  - `STATUS: PICKED <commit_hash> base=<sha>` (exit 0)
  - `STATUS: EMPTY_DELTA base=<sha>` (exit 0)
  - `STATUS: OWNERSHIP_CONFLICT -- <reason>` (nonzero, tree restored clean)
  - `STATUS: ERROR -- <reason>` (nonzero — bad repo/branch/etc.)

**swarm-runner KEEPS** the orchestration: the per-worker loop, COMPLETED/skip
filtering, BUILD_TRACKING row appends, assembly-summary, and the conflict→
preserve-branches→write-report→set-final_status→return sequence. swarm-runner Step 3
becomes "call the tool per worker, branch on its STATUS."

---

## Questions for Codex (answer each, ordered by importance)

1. **Mutation contract / atomicity.** The tool mutates the currently-checked-out
   assembly branch. (a) Should the tool assume the caller already checked out the
   assembly branch (current swarm-runner Step 2 behavior), or should it take an
   `--assembly-branch` arg and check out itself? Weigh coupling-to-caller-state vs.
   the tool mutating HEAD. (b) On a mid-range conflict (commit 3 of 5), is
   `git cherry-pick --abort` + "tree restored clean" a sufficient, verifiable
   post-condition? How should the tool PROVE it left a clean tree (e.g. assert
   `git status --porcelain` empty before returning)?
2. **Is the do-it shape actually safe to fixture deterministically?** It mutates git.
   Our plan: F-A1 builds a hermetic temp git repo with synthetic branches and runs
   the real tool against it. Is a temp-repo fixture sound, or are there git-state
   leaks (global config, GIT_DIR, signing, hooks) that make a mutating-tool fixture
   flaky? How would you isolate it?
3. **Output/exit-code contract.** Is the `STATUS:` line-1 + exit-code convention
   (copied from `check_spec_provenance.py`) the right interface for swarm-runner to
   branch on? Is `PICKED / EMPTY_DELTA / OWNERSHIP_CONFLICT / ERROR` exhaustive and
   mutually exclusive? Where does the merge-commit pre-flight abort map — its own
   status or folded into OWNERSHIP_CONFLICT?
4. **Boundary correctness.** Is "tool = single worker, swarm-runner = loop +
   BUILD_TRACKING + abort-orchestration" the right cut? Anything in lines 76–138 that
   MUST stay in the tool (or MUST stay in swarm-runner) that the proposal gets wrong?
   Specifically: should the BUILD_TRACKING row append move into the tool, or stay in
   swarm-runner?
5. **Detached-HEAD scope.** Keep it out of scope (parity with current prose), or fold
   in `git worktree list --porcelain` detection now since we're touching this anyway?
6. **F-A1 fixture coverage.** Proposed cases: (a) multi-commit worker → asserts ALL
   N commits replayed (the data-loss guard — the reason for do-it); (b) empty-delta
   worker → EMPTY_DELTA; (c) conflicting worker → OWNERSHIP_CONFLICT + clean tree;
   (d) merge-commit worker → pre-flight abort. Is that the right minimal set? Any
   case that would catch a real regression we're missing (e.g. multi-commit WHERE an
   earlier commit would be dropped by `<branch>^` — the explicit negative control)?
7. **Validation sufficiency.** The deferred item says Track A P-extract "requires its
   own real-build validation." Is F-A1 (fixture) + a SCOPED real-orchestrator run
   (like the FC52 `998854e` pre-spawn-halt run) sufficient before this can back a
   suite-adoption gate (#3), or do you require a FULL real swarm build first?
8. **Value/risk check.** Track A is the most battle-tested track (069+070, 0
   conflicts). Does extracting a NEW mutating tool surface for already-working,
   field-proven logic justify the risk — or would you keep it P-accept? (We lean
   extract, to (a) get the range command under test and (b) complete suite coverage
   so #3 can proceed. Push back if you disagree.)
9. **Anything we got wrong** in the boundary, the status set, or the framing.

---

## Output we want

- A recommendation on the **mutation contract** (Q1) and **boundary** (Q4) — these
  shape the tool's signature.
- Answers to Q2–Q9.
- A short proposed outline (bullets, not code) for: the tool's CLI signature +
  status/exit contract, and the F-A1 fixture cases.
- Explicitly: **GO to draft the brainstorm/plan**, or a blocking concern that should
  change the approach (including "keep it P-accept" if you believe that).
