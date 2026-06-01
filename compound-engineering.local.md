# Review Context -- Sandbox Autonomy Hardening

## Risk Chain

**Brainstorm risk:** N/A -- plan was revised directly from prior version, no brainstorm phase

**Plan mitigation:** Burn-zone safety model -- keep autopilot powerful, move all safety to the perimeter (gitignore, secrets policy, data inventory, advisory audit)

**Work risk (from Feed-Forward):** "Whether existing tracked .db, .csv, and .jsonl files contain sensitive material"

**Review resolution:** 5 agents (security, architecture, simplicity, pattern, learnings), 3 P1s fixed (`.env.*` gap, audit filter alignment, verification command sync), 4 P2s (1 fixed, 3 deferred), 5 P3s (1 fixed, 4 accepted). Feed-Forward risk resolved: inventory completed, 2 sensitive files untracked, rest classified safe/generated.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| .gitignore | 12 -> 77 lines, broad sensitive-file coverage | Pattern completeness -- missing types leave gaps |
| .claude/skills/autopilot/SKILL.md | Step 1.55 + Advisory Audit (now delegated to helper skill) | FC11 skip risk for non-blocking steps |
| .claude/skills/advisory-audit/SKILL.md | New helper skill (baseline + report modes) | First real run will validate |
| scripts/sensitive-file-scan.sh | Centralized find command | Single point of failure for audit accuracy |
| CLAUDE.md | Destructive git rewrites added to forbidden actions | Coverage completeness |

## Plan Reference

`docs/plans/2026-05-13-feat-sandbox-autonomy-hardening-plan.md`
