# Review Context -- Sandbox

## Risk Chain

**Brainstorm risk:** N/A (no brainstorm phase -- control-plane hardening derived from analysis)

**Plan mitigation:** Autopilot skill complexity identified as primary risk. 500-line extraction threshold established. Phase 0 resolved control surface scope before implementation.

**Work risk (from Feed-Forward):** "Autopilot skill complexity after this work. If it exceeds ~500 lines, extract verification gates into a separate helper skill."

**Review resolution:** 4 findings from Codex (all fixed in one commit): tool mismatch in spec gate agent, sequencing bug in autopilot skill, CLAUDE.md inaccuracy for out-of-repo writes, spike artifact vs plan mismatch. 0 findings on second pass.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| .claude/skills/autopilot/SKILL.md | +65 lines (gates, spec gate step, non-interactive learnings call) | Complexity -- 455/500 lines. Next addition may trigger extraction. |
| .claude/skills/update-learnings-noninteractive/SKILL.md | New 292-line skill duplicating global command | Duplication drift -- if global command changes, this copy diverges |
| CLAUDE.md | New root operating contract | Accuracy -- must stay in sync with actual skill behavior |
| .claude/agents/spec-consistency-checker.md | New pre-swarm gate agent | Untested in live swarm -- first real test is next swarm build |

## Plan Reference

`docs/plans/2026-05-13-feat-sandbox-autonomy-hardening-plan.md`
