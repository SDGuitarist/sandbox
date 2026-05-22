# Review Context -- Sandbox (Spec Completeness Checker)

## Risk Chain

**Brainstorm risk:** "Whether the completeness checker can reliably parse spec structure to identify routes/functions/exports without excessive false positives."

**Plan mitigation:** Hybrid parsing strategy (canonical heading prefixes, flexible content). Route-path column allowlist with /prefix guard. 3 Codex rounds hardened N/A flow, enumeration rules, and inter-check dependencies.

**Work risk (from Feed-Forward):** Route-table column parsing, Check 2->1 dependency, heading-prefix matching on future formats.

**Review resolution:** 1 P1 (permission mode list) + 5 P2 (CLAUDE.md method gap, commit step, wording, report format, naming) fixed. 2 P2 deferred (template scaffolding, N/A dedup). 9 P3 deferred.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| .claude/agents/spec-completeness-checker.md | New agent, 6 checks, BLOCKED status | Check logic correctness, heading detection |
| .claude/skills/autopilot/SKILL.md | Step 9w.6, permission mode list | Gate integration, retry flow |
| CLAUDE.md | Mandatory spec sections | Documentation accuracy vs agent behavior |

## Plan Reference

`docs/plans/2026-05-21-feat-spec-completeness-checker-plan.md`
