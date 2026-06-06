---
title: "Disk-Verify Delegated STATUS: Inverting Terminal-Gate Authority from Wire to On-Disk Artifact"
date: 2026-06-06
run_id: "plan-A"
category: orchestration-hardening
severity: medium
problem_type: reliability-fix / terminal-gate
build_type: manual
swarm: false
merge: "PR #10 -> master 74660d6"
tags:
  - autopilot
  - swarm-orchestration
  - terminal-gate
  - delegation-architecture
  - context-death
  - durable-artifact-verification
  - fail-closed
  - run-id-reuse
  - plan-deepening
  - codex-review
components:
  - tools/verify_delegated_status.py
  - tests/test_verify_delegated_status.py
  - .claude/skills/autopilot/SKILL.md
  - .claude/agents/tail-runner.md
root_cause: >
  The 3-stage context-death delegation architecture (runs 061/065/068) trusts
  each fresh-context agent's echoed "wire" STATUS line as the run's terminal
  pass/fail verdict. That made a *forgotten Output Contract* a silent chain break:
  in run 068 the tail-runner finished all work but omitted its STATUS echo, and a
  strict "no STATUS line -> FAIL" reading would have failed a genuinely complete
  run. The wire is the known-unreliable channel; the durable on-disk artifact is
  not.
resolution: >
  Moved terminal authority from the echoed wire STATUS to the on-disk artifact via
  a new shared deterministic verifier (tools/verify_delegated_status.py): existence
  + freshness (mtime >= run_start_ts) + run-id match + non-FAIL per-artifact status.
  Wire STATUS is logged, never decisive; disk wins in both directions. Wired into
  both delegation handlers (Steps 11w-16w + Step 18w); run_start_ts added to the
  Step 1 Run State block and captured in Step 5.5; tail-runner Output Contract and
  both TAIL_SYNC_POINT comments updated to record the deliberate solo/swarm
  verification asymmetry. Item 2: worker-roster.md written at Step 10w spawn as
  write-only insurance. 12/12 fixture tests pass. Codex review CLEAN (0 P0, 0 P1).
---

## Problem / Goal

The autopilot swarm pipeline delegates two heavy phases to fresh-context agents
to survive orchestrator context death (the 3-stage delegation architecture from
runs 061/065, validated at 12 agents in run 068):

- **Steps 11w-16w** delegate assembly + verification to the **swarm-runner** agent
  (artifact: `docs/reports/<run-id>/assembly-summary.md`).
- **Step 18w** delegates the review-through-self-audit tail to the **tail-runner**
  agent (artifact: `docs/reports/<run-id>/self-audit.md`).

Each agent echoes a terminal STATUS line back over the wire, and the orchestrator
trusted that echo as the run's pass/fail verdict. The run-068 retrospective surfaced
the failure mode: the tail-runner completed all work but **omitted its Output
Contract echo**. A strict "no STATUS line -> FAIL" reading would have failed a fully
successful run. The wire is a fast-path hint that can be forgotten or truncated; the
durable artifact on disk is the real evidence of completion.

**Goal (Plan A, items 1-2):** move terminal authority to the on-disk artifact
without opening a *stale-STATUS false-PASS* hole (a prior aborted run's PASS artifact
sitting at a reused run-id path), and persist the one piece of orchestrator state
that has no durable home during the spawn window (the role->agentId->branch map).

## What Was Built

### Item 1 — Disk-verify delegated STATUS (the terminal-gate fix)

A new shared script `tools/verify_delegated_status.py` is the single deterministic
disk-verify routine. It returns **PASS (exit 0) only when ALL hold**, else a distinct
non-zero code per failure reason:

| Check | Pass condition | Fail exit |
|-------|----------------|-----------|
| Exists & readable | `os.stat`/open succeeds | `2` MISSING |
| Fresh | `st_mtime_ns >= run_start_ts*1e9` (`>=`) | `3` STALE |
| Run-id match | embedded run-id == `--run-id` | `6` RUNID_MISMATCH |
| Status parses | a recognized terminal token found | `4` NO_STATUS |
| Status non-FAIL | in per-kind accept-set | `1` FAIL_STATUS |
| (CLI errors) | argparse override (not default 2) | `5` BAD_ARGS |

**Per-artifact STATUS extraction** (the key correction — see Risk Resolution):
- `self-audit`: anchor to the `## Final Run Status` section, read its
  `**Status:**` line. Accept-set = `{PIPELINE_PASS, PIPELINE_PASS_WITH_DEFERRED_RISK}`.
- `assembly`: `STATUS:` token on **line 1 only** (no MULTILINE fallback — fail-closed).
  Accept-set = `{PASS}`.

Wiring:
- `run_start_ts` declared in the Step 1 Run State block (SKILL.md) and captured
  (epoch seconds) in Step 5.5 — the freshness reference (nothing recorded run start
  time before).
- Step 18w rewritten to invoke the script against `self-audit.md`; the old
  "no STATUS line -> FAIL" crash branch now defers to the script's existence result.
- Steps 11w-16w handler invokes the script against `assembly-summary.md` **only on a
  PASS wire STATUS**. Blocking-FAIL classes (`contract-check:` / `merge-conflict:`)
  short-circuit *before* any disk-verify — they abort via wire STATUS and the
  artifact may not exist. Existing escalation ordering preserved.
- Mirrored in `tail-runner.md` Output Contract note + **both** TAIL_SYNC_POINT
  comments, recording the deliberate asymmetry: after this change the **swarm** tail
  trusts the on-disk artifact while the **solo** tail still trusts its own inline
  STATUS (solo produces the artifact itself — there is no *delegated* status to verify).

### Item 2 — worker-roster.md at spawn (write-only insurance)

In Step 10w, immediately after the single-message parallel spawn and **before**
awaiting any completion, write `docs/reports/<run-id>/worker-roster.md`:

```
# Worker Roster — run <run-id>
| Role | Agent ID | Branch | Worktree Path |
```

Worktree branches are named `worktree-agent-<agentId>`, not by role, so this mapping
otherwise lives only in volatile orchestrator context and is lost on a mid-spawn
context death. No consumer reads it in this plan (a recovery consumer is deferred) —
it is durable backing for the one piece of state with no other home.

## Key Technical Decisions

### 1. Disk always wins — the wire never vetoes

The verifier's whole reason to exist is that the wire channel is unreliable. So a
fresh, run-id-matching, non-FAIL artifact is **PASS even if `--wire-status` says
FAIL**, and a missing/stale/FAIL artifact is **FAIL even if the wire says PASS**.
Letting the wire veto a disk PASS (a best-practices reviewer suggestion) was
deliberately **rejected** — it would reintroduce the exact false-FAIL this plan
exists to kill. The wire is logged context only.

### 2. Per-artifact extraction, not one "line 1" rule

The two artifacts have *different* STATUS formats. `assembly-summary.md` uses
`STATUS: PASS` on line 1; `self-audit.md`'s line 1 is a heading and its verdict is
`**Status:**` under `## Final Run Status`. A single generic parser would false-FAIL
every real self-audit. (This was caught as a **P0 during deepening** — see Risk
Resolution.)

### 3. Single source of truth preserved

`/verify-self-audit` remains the **sole** authority on deferred-risk disposition
(CLAUDE.md Gate 7f / DEFERRED+HIGH rules). The new verifier treats
`PIPELINE_PASS_WITH_DEFERRED_RISK` as a pass token and stops — it does NOT inspect
WARN dispositions. No live disagreement path exists between the two.

### 4. Fail-closed mechanics

Exit codes kept in 1-255 (256 wraps to 0 = false pass). `st_mtime_ns` integer
compare. STATUS token matched whole (`PASS != BYPASS`). Top-level `try/except` ->
non-zero so an unexpected crash never reads as success. argparse error overridden to
exit 5 (default 2 would collide with MISSING).

### 5. Why a script (honest rationale)

A terminal pass/fail gate decided by LLM prose re-interpretation is fragile, and the
codebase already invokes Python and trusts an exit code at a gate (Step 9w.8 /
`spec_eval_gate.py`). The script centralizes the *decision routine* in one tested
place. It does NOT collapse the TAIL_SYNC_POINT duplication — both call sites still
carry their own one-line "invoke the script with this artifact-kind" instruction.

## Architecture Note: Authority Inversion on the Delegation Substrate

This is not a new architecture — it is an **authority inversion** layered on the
proven 3-stage context-death delegation pattern. Delegation's Output Contract
(`report_path` + a parseable STATUS line) made no-read discipline possible (run 061,
run 065). Plan A keeps the contract but **demotes the wire half of it to a hint** and
promotes the durable half (the artifact on disk) to the verdict. File-based contracts
were always the substrate (agents communicate through the filesystem, not function
calls — run 065 swarm orchestration); this change simply makes the gate read the
substrate instead of the echo. The worker-roster is the same move applied to spawn
state: the cheapest durable backing for orchestrator state with no other home.

## Risk Resolution

**Flagged risk (brainstorm -> plan Feed-Forward):** item 1 changes the run's terminal
gate. A wrong fix opens a *stale-STATUS false-PASS* hole OR a *false-FAIL* via
status-format mis-parse. `verify_first: true`.

**What actually happened — the chain closed cleanly:**

- **Deepening caught TWO P0s before any code was written:**
  1. `self-audit.md` has no line-1 STATUS — the verdict is `**Status:**` under
     `## Final Run Status` (confirmed against the real `docs/reports/068/self-audit.md`).
     A naive "line 1" parser would have false-FAILed every real run.
  2. `PIPELINE_PASS_WITH_DEFERRED_RISK` is a *passing* status (run 068 shipped with
     it). Binary PASS/FAIL was wrong; the accept-set needed both pass tokens.
  Both were missed by the plan-level reviewers who read only the *spec*. The agent
  that caught them read the *live on-disk artifacts*. **Lesson:** in a plan-deepen
  fan-out, assign one agent to verify against the real files, not the abstraction.

- **Code review caught** a lingering non-blocking wire-FAIL abort branch (fixed in
  `5cf36b6`) and confirmed the assembly parser must enforce line-1 STATUS exactly
  with no multiline fallback.

- **A Codex confirmation pass produced a false negative from a stale local checkout**
  — it re-flagged an already-fixed finding because it reviewed a local checkout, not
  the live PR head. Resolved by reviewing `gh pr diff 10` and making the confirmation
  prompt hash-agnostic (`1d12b94`, `817e7ee`).

- **Prior risk verdict (plan Feed-Forward "least confident"):** whether the LLM
  orchestrator would invoke the script and trust its exit code over re-deciding from
  the wire prose. **Held** — the SKILL.md wiring says "exit 0 = PASS, any non-zero =
  FAIL, do not second-guess," consistent with the existing `spec_eval_gate.py` gate.
  The authority is now in the script's exit code, not in prose the model can
  re-interpret.

**ACCEPTED RESIDUAL RISK (documented, NOT closed):** a *future-dated* stale artifact
under a *reused* run-id defeats both the mtime guard (future-dated) and the run-id
guard (run-ids are reused — they derive from the solution-doc count). Consciously
accepted because it requires a backwards system clock on a single-host sandbox
(near-impossible here). The only complete fix is a per-run **nonce** embedded by the
producer agents, which is out of Plan A scope (it edits the producers Plan A holds
invariant). **No acceptance test covers this case — a green suite does NOT imply it
is closed. Revisit trigger:** autopilot running on multi-host / networked-FS infra,
or any observed clock-skew anomaly -> ship the per-run nonce as a new plan.

## Prevention / Patterns

1. **Terminal gates verify the durable artifact on disk, not the agent's echoed wire
   STATUS.** The wire is a hint; a forgotten/truncated contract must not fail a
   complete run, and a stale artifact must not pass an incomplete one. Disk wins in
   both directions. *(agent-pitfalls candidate.)*
2. **Review the PR's remote head, not a local checkout.** A confirmation pass
   false-flagged an already-fixed finding from stale local state. For confirmation
   passes: `git fetch` + `gh pr diff <n>`, and make the prompt hash-agnostic.
3. **In a plan-deepen fan-out, assign one agent to verify against the real on-disk
   artifacts.** That agent caught both P0s the plan-level (spec-only) reviewers
   missed.
4. **Run-ids are reused** (derived from solution-doc count) -> report paths collide
   across aborted runs. Any "is this artifact from THIS run?" check needs an
   independent freshness signal (here: `run_start_ts` + mtime).
5. **When moving authority between channels, record the asymmetry explicitly.** The
   solo tail still trusts its inline STATUS; only the *delegated* (swarm) tail trusts
   disk. Both TAIL_SYNC_POINT mirror sites and the tail-runner Output Contract say so,
   so the two paths don't silently drift.

## Acceptance Verification

`python3 tests/test_verify_delegated_status.py` -> **12/12 passed** (re-run during
compound, exit 0). Covers 5 PASS cases (self-audit `PIPELINE_PASS` no-wire,
`PIPELINE_PASS_WITH_DEFERRED_RISK`, self-audit + assembly with contradicting wire,
freshness boundary `mtime == run_start_ts`) and 7 FAIL cases (missing, stale, run-id
mismatch, `PIPELINE_FAIL`, no-status, assembly-status-not-on-line-1, bad CLI args).
Item 2 verified by documented manual repro; opportunistic confirmation on the next
real swarm build.

## Artifacts

| Item | Location |
|------|----------|
| Brainstorm | docs/brainstorms/2026-06-06-autopilot-orchestration-hardening-brainstorm.md |
| Plan | docs/plans/2026-06-06-autopilot-orchestration-hardening-A-reliability-plan.md |
| Verifier (new) | tools/verify_delegated_status.py |
| Test harness (new) | tests/test_verify_delegated_status.py (12/12) |
| Skill wiring | .claude/skills/autopilot/SKILL.md |
| Tail mirror | .claude/agents/tail-runner.md |
| Merge | PR #10 -> master 74660d6 |

## Cross-References

- `docs/solutions/2026-06-05-autopilot-context-death-delegation-architecture.md` —
  the delegation substrate this inverts authority on.
- `docs/solutions/2026-06-01-tail-delegation-context-resilience.md` — established the
  tail-runner Output Contract STATUS line this now disk-verifies.
- `docs/solutions/2026-04-09-autopilot-swarm-orchestration.md` — file-based agent
  contracts (the substrate); ownership gate pattern.
- `docs/solutions/2026-05-13-sandbox-autonomy-hardening.md` — "enforcement lives in
  the skill, not prose"; the disk-verify exit-code gate is that principle applied to
  the terminal verdict.

## Feed-Forward

- **Hardest decision:** Defining "stale" given run-ids are *reused*. Chose
  `mtime >= run_start_ts` (new `run_start_ts` at Step 5.5) + a free run-id cross-check
  over a per-run nonce. This leaves a consciously accepted residual (future-dated
  artifact at a reused run-id) rather than a silent deferral.
- **Rejected alternatives:** trust the artifact blindly (reopens false-PASS); one
  generic line-1 parser (the two artifacts differ — caught as a P0); wire-vetoes-disk
  (reintroduces the false-FAIL); re-adjudicate deferred-risk in the new script (second
  source of truth); a constant `Spawn Status` roster column; a full failure-injection
  harness for item 2 (would test a fake context-death simulator).
- **Least confident / open for Plan B:** the residual stale-artifact hole stays open
  by design. The trigger to close it (multi-host / networked-FS, or observed clock
  skew) is recorded but not monitored automatically — if the sandbox ever goes
  multi-host, the nonce work must be remembered. Plan B (spec-eval demotion +
  read-path completeness surface) is the next orchestration-hardening increment from
  the same brainstorm.
