# Review Context -- Sandbox (Autopilot Context Optimization)

## Risk Chain

**Brainstorm risk:** Orchestration-load heuristic may false-positive on successful runs (run 048 scores 40.5) or miss future failures (28-agent build with 0 deepening scores 37).

**Plan mitigation:** Set >30 threshold despite false positive. Cost of false positive (brief manual resume) is much cheaper than false negative (context death + lost artifacts). Calibrate after next 2 large swarms.

**Work risk (from Feed-Forward):** Checkpoint placement and BUILD_TRACKING ownership change are structural -- errors here silently corrupt the resume contract.

**Review resolution:** 2 P1s found (dangling reference to removed heuristic component, checkpoint placed before BUILD_TRACKING fill). Both fixed. 4 P2s deferred (all LOW: format inconsistencies, verbose template, shorter error messages).

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| .claude/skills/autopilot/SKILL.md | Incremental BUILD_TRACKING, checkpoint gate, Step 6.1/6.5, solo/swarm conditional | Orchestration flow integrity |
| .claude/skills/tail-resume/SKILL.md | New skill: reads CHECKPOINT.md, runs tail sequence | Resume contract correctness |
| .claude/skills/update-learnings-noninteractive/SKILL.md | --plan and --review-summary argument flags | Backwards compatibility |

## Plan Reference

`docs/plans/2026-05-20-autopilot-context-optimization-plan.md`
