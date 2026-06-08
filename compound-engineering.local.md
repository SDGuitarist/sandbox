---
review_agents:
  - learnings-researcher
  - architecture-strategist
  - code-simplicity-reviewer
  - security-sentinel
---

# Review Context — Sandbox (Autopilot Orchestration Hardening, post-069)

## Risk Chain

**Plan risk (Feed-Forward):** Track A (worktree base) is the highest-blast-radius edit — it touches the assembly path of a pipeline that just ran a clean 24-agent build. The residual unknown: is `git merge-base(original_branch, branch)` always the worker's true fork point, and does cherry-picking the per-worker delta reproduce the working merge path across empty/multi-commit workers?

**Spike mitigation (Phase 0):** Throwaway-repo spike (16/16 + 1 + 5 assertions PASS) resolved it BEFORE any SKILL.md edit. merge-base IS the true fork point; cherry-pick replays all N commits; `<branch>^` drops commits (forbidden); zero-commit = no-op; conflict → clean abort + branches preserved. Strategy (i) uniform cherry-pick chosen (reproduces merge tree; matches 069's clean run).

**Work risk:** demoting a gate (spec-eval) whose own design-time doc argues to keep it hard; and propagating the blocking-class change (`merge-conflict:` → `assembly-ownership-conflict:`) across swarm-runner + orchestrator without breaking the wire-abort handler.

**Review resolution (Codex binding, GO x3):** Round 1 — Track B GO, Track C GO, Track A NO-GO (detached-HEAD pre-flight was dead code: a branch name never resolves to HEAD, runtime has no worktree path). Fixed in `1f4c5bd` (removed; manifests as empty-delta no-op). Round 2 — Track A GO. Constraints confirmed: solo path ≤354 untouched, `original_branch` merge-back untouched, O3 invariant holds, class bookkeeping complete.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| .claude/skills/autopilot/SKILL.md | 9w.8 advisory; 10w precondition removed; ownership base main→original_branch; wire-abort class | swarm-path gates + assembly entry (all below :354) |
| .claude/agents/swarm-runner.md | per-worker merge → cherry-pick; `assembly-ownership-conflict:` class; pre-flight; Step 7 merge-back untouched | assembly correctness, blocking-class propagation |
| .claude/agents/spec-completeness-checker.md | Check 1b orchestration-entrypoint presence guard | pre-swarm coverage (FC50) |
| docs/templates/shared-spec-flask.md, CLAUDE.md | entrypoint row-class + Full Signature column / item 1 | spec authoring contract |
| docs/reports/orchestration-hardening/spike-*.{sh,md} | Phase-0 spike + report | Track A gate evidence |

## Plan Reference

`docs/plans/2026-06-07-refactor-autopilot-orchestration-hardening-plan.md`
