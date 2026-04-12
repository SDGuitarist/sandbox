# Lessons Learned -- Sandbox

Accumulated lessons from 9 builds of the compound engineering automation pipeline.

## Pipeline & Verification

- **Verification pipeline is a safety net, not a quality tool.** It catches mechanical errors (wrong names, missing imports, type mismatches) but NOT design errors (wrong algorithm, missing edge cases, bad UX). Spec violations are the most common swarm failure mode and have unambiguous fixes. (Build #9)
- **Assembly-fix works when contract-check reports include three things:** (1) the specific file and line, (2) what's wrong, (3) what the spec says it should be. The agent doesn't need to understand the app -- it applies the diff between actual and spec. (Build #9)
- **Contract checker found 6/6 injected errors** in one pass. No false positives, no missed violations. The checker is reliable for function name, import, and call-site mismatches. (Build #9)

## Shared Spec Pattern

- **Shared spec is genuinely stack-agnostic.** The critical factor is spec precision (usage examples, prohibition rules), not the framework. Works for Flask and Node/Express with zero structural changes. (Build #7)
- **Prohibition rules in specs prevent the most common swarm failures.** Explicit "do NOT import X in Y" rules stop agents from inventing their own patterns. (Builds #3-#9)
- **Spec precision > agent count.** A precise spec with 3 agents outperforms a vague spec with 5. (Builds #2-#8)

## Swarm Patterns

- **Zero-prompt requires three layers:** Bash Command Rules in SKILL.md + agents, `Bash(git -C *)` in global allowlist, and prescriptive step rewrites. None alone is sufficient. (Build #6)
- **5-agent swarms work without extra coordination.** Cross-module writes are fine when ownership is clear in the spec. (Build #8)
- **One agent per job** -- never overload agents with multiple tasks. Split into separate focused agents. (All builds)

## Review

- **Test harness apps don't need production-grade fixes.** When reviewing a pipeline test app, mark production concerns (auth, input validation, XSS) as "won't fix" if they don't affect the test's purpose. (Build #9)
- **Learnings Researcher agent is highest-ROI review agent.** Solution doc violations are always P1. (Global lesson)
