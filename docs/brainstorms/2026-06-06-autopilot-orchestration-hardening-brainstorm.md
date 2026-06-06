# Brainstorm — Autopilot Orchestration Hardening (Run 068 Retrospective Fixes)

**Date:** 2026-06-06
**Status:** brainstorm
**Source:** Run 068 (Gig Outcome Tracker) retrospective — orchestration-layer findings
**Delivery:** Two plans (A = reliability fixes, B = gate/spec changes)

## What We're Building

Four targeted hardening changes to the autopilot swarm pipeline, surfaced by the
run-068 retrospective. They are process/infra fixes, not new features — each
closes a concrete failure mode observed during a real 12-agent build.

**Plan A — Reliability fixes (small, ship fast):**
*Risk note: item 2 is write-only insurance (zero behavioral risk); item 1 is
small but changes the run's terminal pass/fail gate, so it carries real risk if
done wrong (see the false-PASS hole below) and must ship behind careful
verification. "Small" ≠ "unguarded."*
1. **Disk-verify delegated STATUS.** Step 18w (and the swarm-runner handler)
   must read the named artifact's on-disk STATUS line (e.g. `self-audit.md`
   line 1) as authoritative, instead of trusting the sub-agent's echoed terminal
   STATUS. The tail-runner finished all work but omitted its Output Contract; a
   strict "no STATUS line → FAIL" reading would have failed a successful run.
   **Authority hierarchy (the crux):** the on-disk artifact STATUS is the source
   of truth; the wire STATUS is a fast-path hint; the artifact missing,
   unreadable, or stale (e.g. wrong run-id / older than this run) is a genuine
   FAIL. The fix must distinguish "agent forgot to echo its contract" (real run →
   PASS) from "work genuinely incomplete" (real FAIL) — it must NOT become "trust
   the artifact blindly," which would open a stale-STATUS false-PASS hole.
2. **worker-roster.md at spawn.** The orchestrator writes
   role→agentId→branch→worktree-path to disk immediately after the parallel
   swarm spawn, before any completion arrives. Worktree branches are named
   `worktree-agent-<agentId>`, not the role, so the mapping otherwise lives only
   in volatile orchestrator context and is lost on a mid-spawn context death.

**Plan B — Gate/spec changes (design + separate review):**
3. **Demote spec-eval (9w.8) to advisory.** Gate still runs every build and
   writes its report, but never blocks; Step 10w drops the spec-eval PASS/waiver
   precondition. Define explicit re-promotion criteria. In run 068 the gate
   produced 20/20 false positives, cost a harness-fix commit + a human waiver,
   and yielded zero true findings.
4. **Read-path / no-record spec surface.** Add a 7th mandatory spec-completeness
   surface (each detail/view route's behavior when `get_X` returns None). The
   completeness checker FAILs the pre-swarm gate if it's missing. Three agents
   independently invented redirect/flash fallbacks for unspecified GET behavior
   (benign FC5 instance, one became deferred P3 068-W1).

## Why This Approach

**Two plans, not one.** Items 1–2 are mechanical and small (item 2 zero-risk,
item 1 small-but-touches-the-terminal-gate); items 3–4 carry real design surface
(gate control flow, spec template, checker logic). Bundling would gate the easy
wins behind the harder calls. Ship Plan A first.

**Disk over wire (1).** The whole delegation design rests on reading one STATUS
line for context economy — but that makes a forgotten contract a silent chain
break. Belt-and-suspenders: read the STATUS line, but confirm the named artifact
on disk. Authority moves to the durable artifact.

**Persist the dispatch (2).** Live recurrence of the 2026-06-05 "serialize
implicit state" lesson. A roster file is the cheapest durable backing for the
one piece of orchestrator state with no other home during the spawn window.

**Advisory, not removed (3).** A blocking gate with ~0% precision is net-negative.
But keeping it running (advisory) preserves the precision data we need to decide
*if/when* to re-promote — removing it loses that signal. The structural gates and
the deterministic smoke fixture are the higher-precision quality signals.

**Blocking is correct for read-path (4).** Unlike spec-eval (a low-precision
*judge*), section-existence is deterministic and 100% precision — the "don't
block until proven" rule doesn't apply. Blocking is consistent with surfaces 1–6.

## Key Decisions

- **Scope:** 4 items in. Per-agent spec slices (cut 12× redundant full-spec
  reads) explicitly **deferred** — it's a scaling experiment, not a hardening
  fix; revisit before the 20–25 agent build.
- **Packaging:** Two plans (A reliability, B gate/spec).
- **Spec-eval semantics:** Runs every build, writes report, **never blocks**;
  drop the Step 10w spec-eval precondition; define re-promotion criteria.
- **Read-path surface:** 7th **mandatory** surface, **blocking** in the
  completeness checker.
- **Spec-eval re-promotion criteria:** recall + precision bar. Over ≥N advisory
  runs, re-promote to blocking only if the gate (1) flagged ≥1 genuine spec
  defect the structural gates **missed** (proves unique value) AND (2) kept
  false-positive rate ≤~10% (proves precision). A gate that never catches
  anything real stays advisory. (Exact N and the FP-rate number get finalized in
  Plan B against the harness's output format.)

## Resolved Questions

- **Spec-eval re-promotion criteria** → recall + precision bar (above). Resolved
  2026-06-06.

## Open Questions

### Needs a decision (carry into Plan A/B)
- **How do we verify a rare-failure fix?** Each Plan A item prevents a failure
  that doesn't occur on a normal run (a forgotten Output Contract; a mid-spawn
  context death). Passive observation can't confirm them — verification needs a
  *reproduction* (inject a missing-STATUS artifact; simulate a lost roster). Open
  question: build small failure-injection harnesses for these, or accept them as
  best-effort with a documented manual repro? This shapes Plan A's acceptance
  tests and is the main reason item 1 isn't trivially "done."

### Deferred to planning (HOW, not WHAT)
- Which artifacts beyond `self-audit.md` get disk-verified (assembly-summary?
  per-phase reports?) and the exact STATUS-read/normalize routine.
- `worker-roster.md` exact schema, location (reports dir vs root), and whether
  swarm-runner/Step 10.5w consumes it for recovery vs it being write-only insurance.
- Read-path surface format (table columns; which route classes require it) and
  how the checker detects the heading.
- Whether the spec template ships a read-path example for the Flask standard.
- **TAIL_SYNC_POINT footgun:** Step 18w logic is duplicated between the autopilot
  SKILL.md and `tail-runner.md` (marked with TAIL_SYNC_POINT). Plan A item 1's
  change must be mirrored in both, or the solo and swarm paths drift.

## Feed-Forward

- **Hardest decision:** Whether to demote the spec-eval gate at all vs. invest in
  fixing its precision. Chose demote-to-advisory because a blocking gate with
  zero true findings is actively harmful (waiver overhead + cry-wolf), while
  keeping it advisory preserves the data needed to fix precision later. The risk:
  a future spec defect the gate *would* have caught ships — mitigated because the
  two structural gates + smoke fixture are higher-precision and remain blocking.
- **Rejected alternatives:** One combined plan (gates easy wins behind design
  decisions); removing spec-eval entirely (loses precision data + intent);
  auto-waiving artifact classes while staying blocking (relies on the same weak
  classifier); warn-then-promote for read-path (overkill for a deterministic
  existence check); including per-agent spec slices now (scope creep, it's a
  scaling change not a fix).
- **Least confident:** Whether the advisory window actually closes. The
  re-promotion criteria need ≥N real swarm builds to accumulate a sample — if
  build cadence is low, the gate languishes in advisory indefinitely (the
  "permanently ignored" failure mode). Mitigation to design in Plan B: log each
  advisory run's outcome to a running tally artifact so the sample accrues
  passively and re-promotion is a visible, checkable threshold rather than a
  someday-intention.
