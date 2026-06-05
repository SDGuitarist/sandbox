# HANDOFF -- Sandbox

**Date:** 2026-06-05
**Branch:** master
**Phase:** Autopilot context-death solution — Review in progress (Codex round done, P1s fixed).

## Current State

Two features on master:
1. **Spec eval gate (9w.8)** — COMPLETE. Merged from feat/pitfall-eval-harness.
2. **Autopilot context-death solution** — Review in progress. Codex found 2 P1s, both fixed:
   - P1-1: Added explicit worker_status serialization step after Step 10w agent completion
   - P1-2: Added context budget note acknowledging 20+ agent sufficiency is NOT proven by design alone — first real 20+ build must be monitored
   - **Codex verdict on 20+ agents:** Not proven sufficient. Improvement is real for post-spawn tail, but deepening + worker spawn remain inline.

SKILL.md now has 9w.8 (Spec Eval Gate) and 9w.9 (Ghost-File Cleanup) as sequential pre-swarm steps.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm (eval) | eval-harness/docs/brainstorms/2026-05-24-spec-eval-gate-brainstorm.md |
| Plan (eval) | eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md |
| Solution (eval) | docs/solutions/2026-06-01-spec-eval-gate-pre-swarm-validation.md |
| Calibration | eval-harness/calibration/spec-eval/ (WRC + Ethics Toolkit) |
| Plan (context-death) | docs/plans/2026-06-03-autopilot-context-death-solution-plan.md |

## Deferred Items

- 8 P3s from eval harness review (prompt injection hardening, pathlib consistency, GateConfig as dataclass, redundant blocklist)
- Anti-leniency judge false positive calibration (24 WRC failures need human triage on first real swarm run)

## Three Questions

1. **Hardest decision?** Table filter design — allowlist-by-header with conservative default-skip. Validated by 81% pass rate with 24 genuine failures vs 62% without filtering.
2. **What was rejected?** No filter (62%, $3, 86 false failures). Section-name filter (fragile). LLM classification (adds cost). Percentage threshold >= 80% (waters down gate).
3. **Least confident about?** Whether the 24 WRC failures include false positives from the anti-leniency judge. First real swarm run using this gate will calibrate.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is the sandbox project.
Two items: (1) Spec eval gate is merged and complete. (2) Autopilot
context-death solution needs Review phase — do Codex first, apply fixes,
then Claude Code second review. Focus the Feed-Forward "least confident":
does the reduced swarm-runner scope save enough context for 20+ agent builds?
Diff: `git diff 35b4950..f091760 -- .claude/`. Key files:
.claude/skills/autopilot/SKILL.md, .claude/agents/swarm-runner.md,
.claude/agents/deepen-merge-runner.md.
```
