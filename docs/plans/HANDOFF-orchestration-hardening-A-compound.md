# Compound Handoff — Plan A (Orchestration Hardening, Reliability Fixes)

**Created:** 2026-06-06
**Phase:** work ✅ merged → **compound** (this handoff)
**Merge:** PR #10 → `master` commit `74660d6` (fast-forward; feature branch deleted)

## Next-session prompt (copy-paste)

> Run the **compound phase** for Plan A (autopilot orchestration hardening — reliability
> fixes), now merged to `master` via PR #10.
>
> Read first:
> - `docs/plans/2026-06-06-autopilot-orchestration-hardening-A-reliability-plan.md` (the plan)
> - `docs/brainstorms/2026-06-06-autopilot-orchestration-hardening-brainstorm.md` (source)
>
> Do:
> 1. Run `/workflows:compound` → write a solution doc to `docs/solutions/` with YAML
>    frontmatter. MUST include a `## Risk Resolution` section closing the Feed-Forward
>    chain (see "Risk Resolution inputs" below).
> 2. Run `/update-learnings` (manual build → interactive variant) to propagate lessons to
>    agent-pitfalls.md, LESSONS_LEARNED.md, the daily journal, and project memory.
> 3. Offer the code-explainer on `tools/verify_delegated_status.py`.
>
> This was a **manual** build (plan `swarm: false`), NOT an autopilot run — so the
> autopilot-only required artifacts (BUILD_TRACKING, self-audit report) do NOT apply.
> Compound here = solution doc + learnings propagation.

## What shipped (for the solution doc)

**Item 1 — Disk-verify delegated STATUS (terminal-gate fix).** Moved the run's terminal
pass/fail authority from each delegated agent's echoed *wire* STATUS to the *on-disk*
artifact, via new `tools/verify_delegated_status.py` (existence + freshness `mtime >=
run_start_ts` + run-id match + non-FAIL terminal status; wire STATUS logged, never
decisive; fail-closed). Wired into both delegation handlers (Steps 11w–16w + Step 18w);
`run_start_ts` added to Step 1 Run State + captured in Step 5.5; tail-runner Output
Contract + both TAIL_SYNC_POINT comments updated to record the deliberate solo/swarm
verification asymmetry.

**Item 2 — `worker-roster.md` at spawn.** Step 10w writes role→agentId→branch→worktree
mapping right after the parallel spawn (write-only insurance against mid-spawn context death).

**Files:** `tools/verify_delegated_status.py` (new), `tests/test_verify_delegated_status.py`
(new, 12/12), `.claude/skills/autopilot/SKILL.md`, `.claude/agents/tail-runner.md`.
Producers (`self-audit-reviewer.md`, `swarm-runner.md`) intentionally untouched.

## Risk Resolution inputs (Feed-Forward chain closure)

- **Flagged risk (brainstorm/plan):** item 1 changes the terminal gate; a wrong fix opens
  a stale-STATUS false-PASS hole OR a false-FAIL via status-format mis-parse.
- **What actually happened:**
  - Deepening caught **two P0s before implementation**: `self-audit.md` has no line-1
    STATUS (verdict is `**Status:**` under `## Final Run Status`); and
    `PIPELINE_PASS_WITH_DEFERRED_RISK` is a passing status. Both would have made the gate
    false-FAIL every real run.
  - Code review caught a **lingering non-blocking wire-FAIL abort branch** (fixed `5cf36b6`)
    and that the assembly parser must enforce line-1 STATUS exactly (no multiline fallback).
  - A Codex confirmation pass produced a **false negative from a stale local checkout** —
    resolved by reviewing the live PR head (`gh pr diff 10`).
- **Accepted residual risk (documented, not closed):** a future-dated stale artifact under
  a *reused* run-id defeats both mtime and run-id guards. Accepted (single-host → backwards
  clock near-impossible); revisit trigger = multi-host/networked-FS or observed clock skew
  (would ship a per-run nonce, out of Plan A scope).

## Lessons to propagate (for /update-learnings)

1. **Terminal gates: verify the durable artifact on disk, not the agent's echoed wire
   STATUS** — wire is a hint; a forgotten/truncated contract must not fail a complete run,
   and a stale artifact must not pass an incomplete one. (agent-pitfalls candidate.)
2. **Review the PR's remote head, not a local checkout** — a confirmation pass false-flagged
   an already-fixed finding from stale local state. For confirmation passes, `git fetch` +
   `gh pr diff <n>` and make the prompt hash-agnostic.
3. **In a plan-deepen fan-out, assign one agent to verify against the real on-disk
   artifacts** — that agent caught both P0s the plan-level reviewers missed. (Already in the
   search-agent playbook Pending section.)
4. **Run-ids are reused** (derived from solution-doc count) → reports paths collide across
   aborted runs; any "is this artifact from THIS run?" check needs a freshness signal.

## Then: Plan B (still pending — do NOT start until compound is done)

Plan B = gate/spec changes from the same brainstorm: (3) demote spec-eval gate (9w.8) to
advisory; (4) add a 7th mandatory blocking spec-completeness surface for read-path/no-record
behavior. See the brainstorm + the original planning handoff
`docs/plans/HANDOFF-orchestration-hardening-planning.md`.
