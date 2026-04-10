# Review Context -- Sandbox (Compound Bash Instruction Refactor)

## Risk Chain

**Brainstorm risk:** "Whether the 5 known patterns are ALL the patterns. The
security heuristics are undocumented -- there may be triggers we haven't hit yet."

**Plan mitigation:** Two-layer defense (rules blocks + prescriptive step rewrites).
curl --retry resolved the retry/polling sub-risk. Up-front audit grep catches
forbidden patterns in instruction text before verification build.

**Work risks (from Feed-Forward):**
1. Runtime behavior may differ from instruction text -- Claude could still
   improvise compound commands despite prescriptive instructions.
2. Verification build not yet run -- instruction refactor is text-complete but
   unverified end-to-end.

**Review resolution:** 0 P1, 4 P2, 4 P3 across 4 review agents.
- P2: SKILL.md missing &&/; chaining rule (fixed), rule ordering inconsistent
  (fixed), test-suite-runner Rule 3 ambiguous (fixed), double numbering (fixed)
- P3: assembly-fix over-delivery (accepted), echo rule coverage (fixed with P2),
  parenthetical inconsistency (fixed with P2), Rule 2 two-calls-in-one (accepted)

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| .claude/skills/autopilot/SKILL.md | Bash Command Rules + Steps 10.5w-16w rewrite | Git operation chaining, loop generation |
| .claude/agents/smoke-test-runner.md | Rules block + Rules 1-2 rewrite + Rule 6 tightened | Dependency install, app start/stop, retry polling |
| .claude/agents/test-suite-runner.md | Rules block + Rules 2-3 rewrite | Dependency install, test execution |
| .claude/agents/assembly-fix.md | Rules block added | Diagnostic bash during failure recovery |

## Plan Reference

`docs/plans/2026-04-09-refactor-compound-bash-commands-plan.md`
