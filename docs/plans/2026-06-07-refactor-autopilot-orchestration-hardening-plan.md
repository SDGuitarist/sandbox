---
title: "Autopilot Orchestration Hardening (Post-Run-069): Worktree Base, Verb-Coverage Gate, Spec-Eval Demotion"
type: refactor
status: active
date: 2026-06-07
swarm: false
autonomy_class: manual
tech_stack: Claude Code skill/agent markdown (.claude/) + Python eval-harness
origin: Post-Run-069 orchestration analysis (this session; no brainstorm doc)
feed_forward:
  risk: "Track A (worktree base) is the highest-blast-radius edit: it touches the assembly path of a pipeline that just ran a clean 24-agent build. The worktree base is harness-opaque, so the fix is assembly-layer. The ONE residual unknown that gates a code edit: is `git merge-base(original_branch, branch)` always the worker's true fork point (vs a worker carrying commits that aren't its own), and does cherry-picking the per-worker delta safely reproduce the working merge path across empty/multi-commit workers? Resolve via Phase-0 spike BEFORE any SKILL.md edit. Secondary: Track B's verb check must be a signature-presence guard, NOT a call-site classifier, or it becomes a second 0-precision gate — the exact thing Track C removes."
  verify_first: true
---

# Autopilot Orchestration Hardening (Post-Run-069) ♻️

## Enhancement Summary

**Deepened on:** 2026-06-07 (5 parallel agents: 2× Explore on git worktree-base + merge-base/cherry-pick correctness, architecture-strategist, code-simplicity-reviewer, spec-flow-analyzer). All load-bearing claims disk-verified.

**Key corrections folded in (the deepening found errors in the first draft):**
1. **Ownership gate is THREE-DOT** (`git diff --name-only main...<branch>`, `SKILL.md:647`) — three-dot already diffs against `merge-base(main, branch)`, so it ALREADY does fork-point attribution. The fix is a **one-token `main`→`original_branch`**, not a "replace with merge-base strategy" rewrite. (Verified.)
2. **`spec-eval-verification.md` IS written** — by the harness, on PASS only (`spec_eval_gate.py:348-356`, verified). The FAIL-but-waived path is a **hand-authored, uncodified human convention** (Runs 068, 069), not a "missing writer." Track C's *action* is unchanged; its *rationale* is corrected.
3. **swarm-runner already has inline conflict resolution + a `merge-conflict:` blocking class** (`swarm-runner.md:85-93,178-181`). Run 069's cherry-pick wasn't "no handling" — it was an LLM agent applying a merge-designed conflict step to a divergent base. The new path must be deterministic AND must NOT reuse that inline resolution (it would fabricate a resolution masking an ownership-gate escape).

**Key simplifications folded in:**
4. **Track A ownership change → one token** (`main`→`original_branch`); spike strategy bake-off removed.
5. **Assembly uses ONE robust recipe** — `git cherry-pick $(git merge-base <original_branch> <branch>)..<branch>` (strategy "merge-base range", which handles N-commit workers; the `<branch>^` candidate is ELIMINATED — it silently drops earlier commits = the FC51 data-loss class).
6. **Track B downgraded from a call-site classifier to a signature-presence guard** — removes the plan's #1 false-positive risk (a markdown checker doing call-graph classification = a new 0-precision gate).
7. **Dropped:** the mandated "Base-Divergence Note" artifact (the agent already writes it; assembly-summary already records the cherry-pick base) and the stale "~500-line SKILL.md budget" risk row (file is 1010 lines).

**New considerations discovered (14 acceptance gaps folded into §Acceptance Tests):** TIMED_OUT+divergent exclusion, zero-commit & >1-commit workers, Exit-2 ENV_ERROR vs Exit-1 RETRY sub-codes, tool→constants-only false-N/A, conflict-path collision (2→3 blocking classes), combined single-build validation, ownership-base==cherry-pick-base invariant, advisory-then-later-abort state, mid-abort branch preservation, cross-worker assembly atomicity, and presence-vs-behavior verification.

---

## Overview

Run 069 (24-agent CPAA swarm) succeeded, but its retrospective exposed **three places where the autopilot pipeline only enforces what it explicitly pins or truly gates — and silently improvises everywhere else.** This plan hardens all three, as a **manual** (non-swarm) process change to the `.claude/` autopilot infrastructure.

| Track | Problem (Run 069 evidence) | Failure class |
|-------|----------------------------|---------------|
| **A** | Worker worktrees rooted on `master` (f90aed8), not feat HEAD; swarm-runner applied its merge-designed conflict step to a divergent base; ownership gate diffs against a hardcoded `main` | FC51 |
| **B** | Spec pins model-layer **nouns** but not orchestration **verbs**; 2/2 unpinned route→engine calls diverged (4 review P1s, knowable pre-spawn) | FC50 |
| **C** | Spec-eval gate (9w.8) is **2-for-2 WAIVED_BY_HUMAN** for the same fake cause via a hand-authored verification file; a ~0%-precision blocking gate that's always waived is governance theater | spec-eval-gate-behavior |

**The unifying insight (sharpened by review):** all three are the *same shape* — a gate or assembly step that **looks deterministic but is backstopped by human/LLM improvisation.** Track A codifies the improvisation; Track B prevents the omission that buried it; Track C deletes the gate whose only "pass" path was a hand-fabricated artifact.

## Problem Statement / Motivation

The compounding loop only compounds if every review P1 becomes a pre-spawn gate, and every silent runtime improvisation becomes a deterministic, escalating step. Run 069 paid for these gaps in review fixes (B: 4 P1s), a lucky recovery (A: cherry-pick was conflict-free *only because* ownership was 100% disjoint), and human waiver friction (C: a $2.86 gate whose verdict was pre-decided to be ignored). Left unfixed, the next feature-branch swarm re-hits all three.

## Current-State Research (disk-verified, with line anchors)

**Track A.** `isolation: "worktree"` (`SKILL.md:591`) is the ONLY worktree control — **zero** `git worktree add` anywhere; base is harness-determined and **not controllable from the skill** (confirmed by experiment: plain `git worktree add` roots on the *main working tree's HEAD*, but the Claude Code harness roots workers on the repo default branch regardless of orchestrator branch). Worker branches: `worktree-agent-<id>` (`:601`).
- Ownership gate: `git -C <root> diff --name-only main...<branch>` (`SKILL.md:647`) — **three-dot = merge-base(main, branch) attribution already**; the only defect is the hardcoded `main` (should be `original_branch`).
- Assembly: `git merge --no-ff <branch>` per worker (`swarm-runner.md:75`); merge-back to `original_branch` (`:131`). **`original_branch` is correctly parameterized** (`SKILL.md:689-690,696`) — DO NOT touch. swarm-runner already has inline conflict resolution (`:85-93`) and a `merge-conflict:` blocking class (`:178-181`); it has **no `merge-base`/divergence logic**. Cleanup (`:134-142`) is **skipped on the existing aborts** (branches preserved for inspection).
- Robust git recipes (Explore-verified by experiment): ownership/fork-point = `git merge-base <original_branch> <branch>`; assembly = `git cherry-pick $(git merge-base <original_branch> <branch>)..<branch>` — correct for 1 and N commits; conflict → exit 1 + `^[UAD]{2}` porcelain markers + `git cherry-pick --abort`; the `<branch>^` candidate **silently drops earlier commits** and is eliminated.

**Track B.** `spec-completeness-checker.md` is an **agent**; Check 1 enumerates 4 classes (`:64-69`) and does **column-1 (Name) membership** (`:81-82`) — purely syntactic. A call-site *classifier* (model vs non-model from prose) would be a new semantic judgment = the plan's #1 false-positive risk. Template Export Names Table: `shared-spec-flask.md:194-202` (`Name | Type | Defined By | Used By`; `Type` is an open enum). CLAUDE.md "Mandatory Spec Coverage Sections" item 1 lists the 4 checked classes.

**Track C.** Step 9w.8 (`SKILL.md:487-519`) blocks via Exit-1 → retry → **abort** (`:513-514`); Exit-1 is **overloaded** (FAIL / WARN_UNSCORABLE / RETRY, `:506-509`); Exit-2 = ENV_ERROR hard abort (`:510-512`). The harder block is the **Step 10w precondition** (`:549-558`): requires `spec-eval-verification.md` with `STATUS: PASS`. **Writer (verified):** the harness writes that file **on PASS only** (`spec_eval_gate.py:348-356`); on FAIL the 068/069 waiver hand-authored it — an **uncodified convention**. **No coded reader elsewhere:** self-audit-reviewer + verify-self-audit have **zero** spec-eval references (verified) → demoting orphans no coded gate. No CLAUDE.md escalation rule references spec-eval (the `:82` rule is the *contract*-checker).

**Regression guard (all tracks):** the **solo path** (Step 7s, branch point `SKILL.md:352-357`) touches none of worktrees, ownership gate, 9w.6, 9w.8, or swarm-runner — all `SWARM ONLY`. No Track can regress solo if edits stay below the branch point.

## Proposed Solution

### Track A — Codify base-divergence-aware assembly (assembly-layer, not spawn)

1. **Ownership gate (`SKILL.md:647`) — one-token fix:** `main...<branch>` → `<original_branch>...<branch>` (keep the three-dot operator; it already attributes the fork-point delta). This makes the gate correct on any feature branch and uses the **same base** as the cherry-pick (§O3 invariant).
2. **Assembly (`swarm-runner.md`) — one robust recipe:** per COMPLETED worker, `git cherry-pick $(git merge-base <original_branch> <branch>)..<branch>` onto the assembly branch. **Spike-resolved decision:** either (i) **uniform cherry-pick for all workers** (simpler, one path) or (ii) **keep `git merge --no-ff` when `git merge-base --is-ancestor <original_branch> <branch>` is true and cherry-pick only the divergent case** (lower blast radius on the currently-working mergeable path, but two paths + a new conflict class). Default to (ii) unless the spike proves (i) reproduces the merge result across the empty-commit and multi-commit edge cases. Record the per-worker cherry-pick base in `assembly-summary.md` (already emitted).
3. **Conflict = ownership-gate escape, not a mergeable conflict:** under enforced disjoint ownership (Step 10.5w), a cherry-pick CANNOT conflict unless ownership was violated. So on a cherry-pick conflict: **do NOT invoke the inline spec-based resolution at `swarm-runner.md:85-93`** (it would fabricate a resolution and mask the violation); abort directly with `git cherry-pick --abort`, **preserve all worker worktrees/branches** (skip Step 8 cleanup, matching the existing abort classes), and record a new blocking class **`assembly-ownership-conflict:`**. **Blocking-class bookkeeping is strategy-dependent (resolved with the Phase-0 strategy choice):** under **(ii)** the merge path is retained, so the count goes **2→3** (`contract-check:` + `merge-conflict:` + `assembly-ownership-conflict:`); under **(i)** the merge path is removed, so `merge-conflict:` is **retired and replaced** by `assembly-ownership-conflict:` (count stays 2). Either way, update swarm-runner's class list (`:178`), the Output Contract abort cases, and confirm the self-audit WARN handling accepts the resulting set (verified: no hardcoded enum rejects an added class).
4. **Exclude non-COMPLETED workers:** the ownership gate AND the cherry-pick run **only over the `worker_status` COMPLETED set** (`SKILL.md:631-635`); TIMED_OUT/FAILED branches are skipped from both, never cherry-picked.

**Must NOT change:** the `original_branch` merge-back target (`SKILL.md:689`, `swarm-runner.md:131`).

### Track B — Orchestration-entrypoint coverage as a signature-presence guard (not a parser)

1. **Template (`shared-spec-flask.md`):** require an **"Orchestration Entrypoints"** row-class in the Export Names Table — every route→non-model function call and tool→constants import that crosses an agent/cluster boundary, with `Type = orchestration entrypoint` and a populated **`Full Signature`** column (name + param types/names + return type + defining agent).
2. **CLAUDE.md "Mandatory Spec Coverage Sections" item 1:** add orchestration entrypoints as a 5th machine-checked class.
3. **spec-completeness-checker — presence guard (reuses Check 1's mechanism, no new parser):** for any Export Names row with `Type = orchestration entrypoint` (the template requires both route→non-model calls AND tool→constants imports to be listed as such rows), FAIL if its `Full Signature` cell is empty. **N/A only when zero `orchestration entrypoint` rows are present** (the guard checks what IS declared; it cannot detect a row the planner omitted — see the blind spot below). **Explicit coverage tradeoff (documented, accepted):** this guards *listed* entrypoints (the demonstrated 069 failure mode — B2/B3 import name, C1/C6 arity were on listable entrypoints); a **wholly-omitted** call is caught downstream by the assembly contract-check, not pre-spawn. We deliberately do NOT build a call-site classifier, to avoid a second 0-precision gate.

### Track C — Demote spec-eval (9w.8) to advisory/non-blocking

1. **Step 9w.8 (`SKILL.md:496-514`):** on Exit-1 **FAIL/WARN_UNSCORABLE**, log the result to BUILD_TRACKING + report and **PROCEED** (advisory); drop tighten→retry→abort. On Exit-1 **RETRY** sub-code, retry **once** before recording the advisory (so a transient API blip isn't logged as a spec advisory). On **Exit-2 ENV_ERROR**, record a **distinct** advisory warning naming it an *environment fault, not a spec pass*, and proceed (do not let a permanently-broken harness masquerade as a clean run).
2. **Step 10w precondition (`SKILL.md:549-558`):** **remove** the `spec-eval-verification.md` + `STATUS: PASS` requirement. (The harness still writes that file on a genuine PASS — now harmless/unused; on FAIL no hand-authored file is needed.) Keep requirement #1 (`gate-verification.md` CLEARED) so the **structural gates 9w.5/9w.6 remain blocking** — the high-precision signals.
3. **No script change** (`spec_eval_gate.py` already returns a code the skill can ignore). **No CLAUDE.md escalation change.** Add a **regression-grep** confirming zero other surfaces read `spec-eval-verification.md`.

## Phase 0 — Verify-First Spike (MANDATORY, gates Track A)

Per the proven tail-delegation pattern (`docs/solutions/2026-06-01-tail-delegation-context-resilience.md`): resolve the riskiest assumption in isolation BEFORE any SKILL.md edit. **Spike file:** `docs/reports/orchestration-hardening/spike-worktree-base.md`.

**Two decision-relevant questions (root-cause "why master" is NOT needed — the fix is base-agnostic):**
1. **Is `git merge-base(<original_branch>, <branch>)` always the worker's true fork point**, and does `git cherry-pick merge-base..branch` replay **all N** of a worker's commits (test 1-commit AND 3-commit workers; confirm `<branch>^` would have dropped commits)? Does a **zero-commit** worker degrade to a clean no-op (not an error)? **This decides strategy and forces the merge-base range over `<branch>^`.**
2. **Assembly routing test (two cases):** a disjoint divergent worker → clean cherry-pick; two workers touching the **same file** on a divergent base → deterministic conflict → `assembly-ownership-conflict:` abort with `--abort` + clean tree + **branches preserved**. If pursuing strategy (i), also confirm uniform cherry-pick reproduces the `merge --no-ff` tree for an is-ancestor (mergeable) worker incl. an empty-commit worker.

**Out of scope (Codex watch item, accepted):** merge-commit and detached-HEAD worker branches are NOT first-class states — the harness produces linear, single-author worker branches. If the spike or a real build encounters either, the assembly **pre-flight aborts loudly** (`git rev-parse --abbrev-ref HEAD` == `HEAD` → detached; `git rev-list --merges <merge-base>..<branch>` non-empty → merge commit) rather than mis-attributing or silently dropping changes. The spike confirms the pre-flight fires; it does not attempt to *handle* these states.

**Exit criterion:** both answered with evidence; strategy (i vs ii) chosen; the ownership-base and cherry-pick-base confirmed identical; the merge-commit/detached-HEAD pre-flight verified to abort.

## Implementation Phases

**Order: lowest blast radius first; Track A last and spike-gated.**

#### Phase 1 — Track C (spec-eval demotion)
- Correct the 069 narrative first (writer exists on PASS; waiver was hand-authored) so Track B's justification rests on accurate history.
- Edit Step 9w.8 (advisory; RETRY/ENV_ERROR handling) + Step 10w precondition (remove spec-eval PASS requirement). Add the S4 regression-grep.

#### Phase 2 — Track B (verb-coverage presence guard)
- Update `shared-spec-flask.md` + CLAUDE.md item 1; add the presence-guard check to `spec-completeness-checker.md`.
- Backtest: CPAA Run 069 plan (now pins entrypoints) → PASS; `docs/fixtures/unpinned-entrypoint-spec.md` (orchestration-entrypoint row with empty Full Signature) → FAIL; model-only fixture → N/A.

#### Phase 3 — Track A (assembly) — spike-gated
- Only after Phase 0. Edit `SKILL.md:647` (one token) + `swarm-runner.md` (cherry-pick recipe + `assembly-ownership-conflict:` class + 2→3 blocking-class bookkeeping + COMPLETED-only scope). Do NOT touch the `original_branch` merge-back.

#### Phase 4 — Binding review + validate-on-real-build
- Codex review (2–3 rounds — the documented norm for SKILL.md edits) BEFORE merge.
- `verify_first` proof on the **next real feature-branch swarm build, exercising all three tracks in ONE run**; validation is complete ONLY if that run's reports contain all three artifacts (9w.6 PASS, advisory spec-eval log, per-worker cherry-pick base in assembly-summary). A 9w.6 false-FAIL that aborts before Track A runs = validation incomplete, NOT pass.

## System-Wide Impact

- **Interaction graph:** A sits at 10.5w (ownership) → 11w-16w (assembly); B at 9w.6 (pre-spawn); C at 9w.8 → 10w precondition. None fire on the solo path (below branch point `:354`).
- **Error propagation:** A *adds* the `assembly-ownership-conflict:` escalation (more visible than today's improvisation) and **disables** inline resolution on that path. C *removes* the spec-eval abort but keeps the two structural aborts; the **advisory log replaces the waiver artifact** as the self-audit's spec-eval input.
- **State lifecycle:** cherry-pick is per-worker; on abort → `--abort` + clean tree + **branches preserved** (no Step 8 cleanup) + assembly branch **never merged to `original_branch`** (Step 7 gated) so `original_branch` is untouched. Advisory-then-later-abort marks the spec-eval entry "advisory only — spawn not reached," not forward progress.
- **Blocking-class enum:** the assembly-abort class set changes (strategy-dependent: +1 under (ii), or replace-`merge-conflict:` under (i)) and must propagate to the Output Contract and any self-audit WARN handling (verified: no hardcoded rejector today).
- **Solo/mergeable invariants:** unchanged; `original_branch` merge-back untouched; regression-grep on `SKILL.md:352-387`.

## Acceptance Tests (EARS)

### Happy Path
- WHEN the ownership gate runs on a worker branch rooted on a base other than `original_branch` THE SYSTEM SHALL attribute only the worker's fork-point delta (`<original_branch>...<branch>`, three-dot). Verify: `bash docs/reports/orchestration-hardening/spike-ownership.sh` — synthetic worker on a stale base lists only its files.
- WHEN a divergent worker has N>1 commits THE SYSTEM SHALL cherry-pick the full `merge-base..branch` range and the assembled tree SHALL contain every file from all N commits. Verify: spike 3-commit branch → all 3 files present post-assembly (proves merge-base range; `<branch>^` would fail).
- WHEN a divergent worker has zero commits beyond its base THE SYSTEM SHALL treat it as a clean no-op (no cherry-pick, no ownership violation). Verify: spike empty branch → assembly proceeds, summary notes empty delta.
- WHEN the ownership gate and the cherry-pick run on the same worker THE SYSTEM SHALL compute an identical base (`merge-base(original_branch, branch)`). Verify: grep both surfaces for the same base expression; spike asserts gate-validated file set == cherry-picked file set.
- WHEN a plan pins every route→non-model and tool→constants entrypoint with a Full Signature THE SYSTEM SHALL PASS the orchestration-entrypoints guard. Verify: checker vs `docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md` → PASS.
- WHEN spec-eval returns Exit-1 FAIL THE SYSTEM SHALL record an advisory result and PROCEED to spawn with no human waiver. Verify: trace shows the next executed step after a simulated Exit-1 FAIL is 9w.9 (spawn path), not an abort.
- WHEN the next feature-branch build runs THE SYSTEM SHALL exercise all three tracks in one run; validation completes only if its reports contain the 9w.6 PASS, the advisory spec-eval log, AND a per-worker cherry-pick base. Verify: one run's reports dir contains all three; any missing = incomplete.

### Error Cases
- WHEN two workers touch the same file on a divergent base THE SYSTEM SHALL detect the cherry-pick conflict, NOT invoke inline spec-resolution, run `git cherry-pick --abort`, preserve all worker branches, leave `original_branch` untouched, and record `assembly-ownership-conflict:`. Verify: `bash docs/reports/orchestration-hardening/spike-conflict.sh` — `git status --porcelain` empty AND worker branches still exist AND `git log original_branch` unchanged AND class recorded.
- WHEN a worker is TIMED_OUT or FAILED THE SYSTEM SHALL exclude its branch from BOTH the ownership gate and the cherry-pick, regardless of commits. Verify: spike divergent branch marked TIMED_OUT → appears in `preserved_branches`, not cherry-picked; gate never runs against it.
- WHEN spec-eval returns Exit-1 RETRY THE SYSTEM SHALL retry once before recording the advisory. Verify: forced transient → BUILD_TRACKING shows one retry, not an immediate advisory.
- WHEN spec-eval returns Exit-2 ENV_ERROR THE SYSTEM SHALL record a distinct advisory warning naming it an environment fault (not a spec pass) and proceed. Verify: `grep` BUILD_TRACKING after an env-faulted run → contains "spec-eval ENV_ERROR (advisory, no spec verdict)".
- WHEN spec-eval logs an advisory proceed and a later pre-spawn gate (9w.9 ghost-file / 10w path-validation) aborts THE SYSTEM SHALL mark the spec-eval entry "advisory only — spawn not reached," not a completed phase. Verify: force a ghost-file abort after advisory → BUILD_TRACKING shows spawn not reached.
- WHEN a plan lists a tool→constants import as an `orchestration entrypoint` row with an empty Full Signature THE SYSTEM SHALL FAIL (a route→non-model call is not required for the guard to fire). Verify: constants-only fixture (one `orchestration entrypoint` row, empty Full Signature) → FAIL naming the symbol. N/A only when zero such rows exist.

### Verification Commands (behavioral where it matters)
- `bash docs/reports/orchestration-hardening/spike-worktree-base.sh` — Phase 0 (fork-point + N-commit + zero-commit + conflict-abort routing). Asserts *behavior*, not token presence.
- `grep -n "merge-base\|cherry-pick\|assembly-ownership-conflict" .claude/agents/swarm-runner.md` — codified (presence smoke-check); the spike asserts the routing actually taken.
- `grep -n "original_branch\.\.\.\|main\.\.\." .claude/skills/autopilot/SKILL.md` (line ~647) — base is `original_branch`, not `main`.
- `grep -rn "spec-eval-verification" .claude/` — only the (now-removed) Step-10w lines; **zero** in self-audit/verify-self-audit/HANDOFF (S4 regression).
- `grep -n "Orchestration Entrypoints\|orchestration entrypoint" docs/templates/shared-spec-flask.md .claude/agents/spec-completeness-checker.md CLAUDE.md` — present on all three (presence smoke-check; the fixture FAIL test is the binding behavioral proof).
- Solo regression: `sed -n '352,387p' .claude/skills/autopilot/SKILL.md` — unchanged.

## Plan Quality Gate (the 4 questions)

1. **What exactly is changing?** (A) `SKILL.md:647` one token + `swarm-runner.md` cherry-pick recipe / `assembly-ownership-conflict:` class / 2→3 bookkeeping / COMPLETED-only scope; (B) `shared-spec-flask.md` + CLAUDE.md item 1 + a presence-guard check in `spec-completeness-checker.md`; (C) `SKILL.md` Step 9w.8 (advisory + RETRY/ENV_ERROR) + Step 10w precondition removal + S4 regression-grep.
2. **What must NOT change?** Solo path (≤ branch point `:354`); the `original_branch` merge-back; the blocking status of 9w.5/9w.6 and the two existing swarm-runner abort classes' behavior; `spec_eval_gate.py`; the mergeable-case assembled tree (if strategy ii).
3. **How will we know it worked?** The EARS criteria, validated by the Phase-0 spike (behavioral) and one combined real feature-branch build producing all three artifacts.
4. **Most likely way this plan is wrong?** Track A: a worker carries commits that aren't its own (non-fork-point merge-base) or an empty/merge-commit edge case the spike under-tests → cherry-pick mis-attributes or stalls; resolved by Phase 0 before any edit. Track B: the presence guard's accepted blind spot (wholly-omitted entrypoints) lets a future omission through to assembly — accepted, because building the classifier risks a worse 0-precision gate.

## Alternatives Considered

- **Pass a base ref to `isolation:"worktree"` at spawn (A).** Rejected: no harness parameter, no `git worktree add` to modify (experiment-confirmed).
- **Orchestrator rebases workers onto feat HEAD (A).** Rejected: rewrites worker history, re-introduces conflict risk; cherry-picking disjoint deltas is the minimal correct design.
- **`<branch>^..<branch>` ownership/assembly (A).** Rejected: silently drops earlier commits on multi-commit workers = the FC51 data-loss class.
- **Full call-site-classifying completeness check (B).** Rejected: prose-level model/non-model classification = a new 0-precision gate; the presence guard catches the demonstrated 069 failure mode.
- **Per-run spec-eval human waiver (C).** Rejected: 2-for-2 governance debt; the hand-authored verification file is itself the improvisation Track A exists to kill.
- **Fix spec-eval harness precision instead of demoting (C).** Deferred (documented re-promotion path), not rejected; demotion is the correct NOW move at 0% observed precision.

## Risk Analysis & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Track A regresses the working assembly | HIGH | Spike-gate (Phase 0); default to strategy (ii) preserving the merge path unless spike proves (i) safe; Codex review pre-merge |
| Conflating ownership-diff base with merge-back target | HIGH | Explicit "do NOT change `original_branch`" guard + verification grep |
| New `assembly-ownership-conflict:` class unknown to self-audit | MED | Update Output Contract + 2→3 bookkeeping; verified no hardcoded enum rejects it; regression check |
| Presence guard misses a wholly-omitted entrypoint | MED (accepted) | Documented tradeoff; assembly contract-check is the backstop; 069 failures were on listable entrypoints |
| Demoting spec-eval hides a future real defect | MED | 9w.5/9w.6 stay blocking; Track B adds the verb coverage that was the actual 069 gap; spec-eval still runs for data |
| ENV_ERROR becomes a silent no-op | MED | A single ENV_ERROR records a distinct advisory warning naming the env fault. **Cross-run escalation of a persistently-broken harness is OUT OF SCOPE for this plan** (it needs cross-run state tracking) — noted as a follow-up, not deferred-within-scope |

**Rollback:** each track is isolated to its own files (Track A: `swarm-runner.md` + one line of `SKILL.md`; B: checker + template + CLAUDE.md; C: two `SKILL.md` steps). A `git revert` of a track's commit restores prior behavior — the edits are surgical and carry no data migration, so rollback is clean and independent per track.

## Feed-Forward

- **Hardest decision:** Reframing Track A from "pin the worktree base" (impossible — harness-opaque) to "codify base-divergence-aware assembly," and then the strategy (uniform cherry-pick vs keep-merge-fork) — deferred to the spike because it hinges on empirical edge-case behavior (empty/multi-commit), not opinion.
- **Rejected alternatives:** spawn-layer base ref; orchestrator rebase; `<branch>^` attribution; call-site classifier; per-run waivers. See §Alternatives.
- **Least confident (VERIFY FIRST):** whether `merge-base(original_branch, branch)` is always the worker's true fork point and cherry-pick reproduces the merge result across empty/multi-commit workers. Phase 0 (two throwaway agents) resolves this BEFORE any SKILL.md edit; until it passes, Track A does not touch the live pipeline.

## Codex Handoff Prompt (binding review — after plan/deepen, before work)

> You are reviewing a plan to harden the Claude Code autopilot infrastructure (`.claude/`) after a clean 24-agent swarm (Run 069). Overriding constraint: **do not regress the working swarm or the solo path.** Plan: `docs/plans/2026-06-07-refactor-autopilot-orchestration-hardening-plan.md`. The plan was deepened and several first-draft factual errors were corrected (ownership gate is three-dot/merge-base already; `spec-eval-verification.md` is harness-written on PASS; swarm-runner already has a `merge-conflict:` class) — verify those corrections are right.
>
> Three tracks: (A) codify base-divergence-aware cherry-pick assembly + a `assembly-ownership-conflict:` class, with a one-token ownership-gate fix (`main`→`original_branch`); (B) a signature-PRESENCE guard for orchestration entrypoints in the 9w.6 completeness gate (NOT a call-site classifier); (C) demote spec-eval 9w.8 to advisory and remove the Step-10w `spec-eval-verification.md STATUS:PASS` precondition.
>
> Scrutinize: (1) **Track A** — is `git merge-base(original_branch, branch)` the correct fork point in ALL cases (worker with >1 commit, merge commit on a worker branch, zero-commit worker, detached HEAD), and is the strategy (i uniform vs ii keep-merge-fork) decision correctly deferred to the spike? Does disabling inline resolution on the cherry-pick conflict path correctly surface an ownership-gate escape rather than masking it? Is the 2→3 blocking-class change fully propagated? (2) **Track C** — confirm the corrected premise (harness writes the file on PASS; FAIL-waive was hand-authored); does removing the precondition leave ANY consumer dangling (self-audit/verify-self-audit/HANDOFF)? Are the Exit-1 RETRY and Exit-2 ENV_ERROR sub-cases handled so a transient/broken harness can't masquerade as a clean run? (3) **Track B** — is the presence-guard's accepted blind spot (wholly-omitted entrypoints) genuinely backstopped by the assembly contract-check, and is the N/A-only-if-both-patterns-absent rule correct? (4) **Solo safety** — confirm every edit is below `SKILL.md:354`. (5) Is the Phase-0 spike (2 questions) sufficient to de-risk Track A, or is a cheaper/safer validation available? Return GO/NO-GO per track with the minimal fix for any issue.

## Sources & References

- **Origin:** Post-Run-069 orchestration analysis (this session).
- **Failure classes:** `~/.claude/docs/agent-pitfalls.md` — FC50 (orchestration entrypoints), FC51 (worktree base divergence).
- **Run 069 evidence:** `docs/reports/069/assembly-summary.md`, `docs/solutions/2026-06-07-cpaa-event-replay-simulator-24-agent-swarm-build.md`.
- **Spec-eval history:** `docs/solutions/2026-06-01-spec-eval-gate-pre-swarm-validation.md`, memory `spec-eval-gate-behavior`.
- **Checker origin:** `docs/solutions/2026-05-21-spec-completeness-checker-pre-swarm-gate.md`.
- **Safe-skill-edit pattern:** `docs/solutions/2026-06-01-tail-delegation-context-resilience.md`, `docs/solutions/2026-05-13-sandbox-autonomy-hardening.md`.
- **Verified code anchors:** `SKILL.md:591` (isolation), `:647` (three-dot ownership base), `:689` (original_branch), `:487-519` (9w.8), `:506-512` (exit-code overload), `:549-558` (10w precondition), `:631-635` (TIMED_OUT skip), `:352-357` (branch point); `swarm-runner.md:75,85-93,131,134-142,178-181`; `spec-completeness-checker.md:64-69,81-82`; `shared-spec-flask.md:194-202`; `spec_eval_gate.py:348-356` (verification-file writer, PASS only).
