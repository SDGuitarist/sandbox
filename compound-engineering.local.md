# Review Context -- Sandbox (Autonomy Hardening)

## Risk Chain

**Brainstorm risk:** Autopilot skill complexity -- all enforcement in one 413-line file.

**Plan mitigation:** Extract verification gates to a helper skill if the skill exceeds ~500 lines.

**Work risk (from Feed-Forward):** Self-audit agent quality -- whether "What Was Missed" and "Skeptical Questions" are consistently substantive.

**Review resolution:** 3 Codex rounds found 9 issues (2H, 2M, 1L + 4 round 2). Key fixes: stable WARN keys replaced prose matching, current-run scoping excluded pre-existing debt, gate logic extracted to verify-self-audit helper skill. All issues resolved. LGTM round 3.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| .claude/agents/self-audit-reviewer.md | New -- post-run self-audit agent | WARN scope boundary (lines 40-61), key format, section completeness |
| .claude/skills/verify-self-audit/SKILL.md | New -- 8 hard gates | Gate 4 solo edge case (sparse dir), Gate 6 leniency |
| .claude/skills/autopilot/SKILL.md | +43 lines (498 total) | Solo run-id (Step 7s.0), delegation to helper skill |
| CLAUDE.md | +3 lines | Self-audit as required artifact #5 |

## Plan Reference

`docs/plans/2026-05-13-feat-sandbox-autonomy-hardening-plan.md`
