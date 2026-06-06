# Planning Handoff — Autopilot Orchestration Hardening

**Created:** 2026-06-06
**Phase:** brainstorm → plan
**Brainstorm doc (read first):** `docs/brainstorms/2026-06-06-autopilot-orchestration-hardening-brainstorm.md`

## Next-session prompt (copy-paste)

> Read `docs/brainstorms/2026-06-06-autopilot-orchestration-hardening-brainstorm.md`.
> It is reviewed and ready. Produce **two** plans via the plan flow
> (plan → deepen → self-review → Codex handoff), Plan A first:
>
> - **Plan A — Reliability fixes:** (1) disk-verify delegated STATUS (read the
>   named artifact's on-disk STATUS as authoritative, wire STATUS is a hint,
>   missing/stale/unreadable artifact = genuine FAIL — do NOT open a stale-STATUS
>   false-PASS hole); (2) write `worker-roster.md` at spawn time
>   (role→agentId→branch→worktree-path) before any completion.
> - **Plan B — Gate/spec changes:** (3) demote spec-eval gate (9w.8) to advisory
>   (runs every build, writes report, never blocks; drop the Step 10w spec-eval
>   precondition; re-promotion = recall+precision bar: ≥1 real defect the
>   structural gates missed AND ≤~10% FP rate over ≥N runs — set N + the exact FP
>   number here); (4) add a 7th **mandatory, blocking** spec-completeness surface
>   for read-path / no-record behavior (each record-fetching read route defines
>   what it does when `get_X` returns None) + completeness-checker enforcement.
>
> Each plan must satisfy the Plan Quality Gate (4 questions), include EARS
> acceptance tests + Verification Commands, a Feed-Forward section, and a Codex
> handoff prompt. Resolve the one open decision below in Plan A.

## Decisions already locked (do not re-litigate)
- Scope = these 4 items. **Per-agent spec slices is deferred** (scaling experiment, revisit before the 20–25 agent build).
- Two plans, Plan A ships first.
- Spec-eval → advisory, runs-but-never-blocks, recall+precision re-promotion bar.
- Read-path surface → 7th mandatory, blocking (deterministic existence check, so blocking is correct).

## Open decision to resolve during planning
- **Verification of rare-failure fixes (Plan A):** these prevent failures that
  don't happen on a normal run (forgotten Output Contract; mid-spawn context
  death). Decide: build small failure-injection harnesses (inject a missing/stale
  STATUS artifact; simulate a lost roster) vs. accept best-effort with a
  documented manual repro. This shapes Plan A's acceptance tests.

## Files likely in scope (verify during planning, don't assume)
- **Plan A:** `.claude/skills/autopilot/SKILL.md` (Step 18w; Step 10w spawn/roster), `.claude/agents/tail-runner.md` (Output Contract / Step 9-10), `.claude/agents/swarm-runner.md` (handler STATUS). **TAIL_SYNC_POINT:** Step 18w logic is duplicated between SKILL.md and tail-runner.md — mirror any change in both.
- **Plan B:** `.claude/skills/autopilot/SKILL.md` (Steps 9w.8, 10w precondition), `.claude/agents/spec-completeness-checker.md` (add 7th surface), the Flask shared-spec template (`docs/templates/shared-spec-flask.md`), and the spec-eval advisory-tally artifact design.

## Provenance
- Source: Run 068 retrospective (Gig Outcome Tracker). Lessons already propagated to `workflow_lessons.md`, `patterns_swarm_spec.md`, `spec-eval-gate-behavior.md`, `LESSONS_LEARNED.md`, agent-pitfalls FC5, and the run-068 solution doc's "Process & Orchestration Findings" section.
