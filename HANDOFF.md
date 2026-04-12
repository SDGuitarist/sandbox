# HANDOFF -- Sandbox

**Date:** 2026-04-12
**Branch:** master
**Phase:** Build #9 complete -- error injection pipeline recovery validated

## Current State

Build #9 (error-test-app): First error injection test. Deliberately gave routes agent wrong function names. Pipeline (spec-contract-checker -> assembly-fix -> smoke-test) detected and recovered all 6 errors in one pass.

### Build History

| # | App | Stack | Agents | Files | Result | Novel |
|---|-----|-------|--------|-------|--------|-------|
| 1 | habit-tracker | Python | 1 | 1 | PASS | Solo path |
| 2 | task-tracker | Flask | 4 | 19 | PASS | First swarm |
| 3 | bookmark-manager | Flask | 3 | 17 | PASS | Tags, endpoint registry |
| 4 | recipe-organizer | Flask | 3 | 24 | PASS | Junction tables |
| 5 | finance-tracker | Flask | 3 | 23 | PASS | Money conversion |
| 6 | contact-book | Flask | 3 | 11 | PASS | Zero-prompt milestone |
| 7 | notes-api | Node/Express | 3 | 11 | PASS | Stack-agnostic |
| 8 | project-tracker | Flask | 5 | 25 | PASS | 5-agent scale + cross-module writes |
| 9 | error-test-app | Flask | 3 | 7 | PASS | Error injection -- pipeline recovery validated |

### Key Lesson from Build #9

The verification pipeline is a **safety net, not a quality tool**. It catches mechanical errors (wrong names, missing imports, type mismatches) but NOT design errors (wrong algorithm, missing edge cases, bad UX). This is correct -- spec violations are the most common swarm failure mode and have unambiguous fixes.

Assembly-fix works when the contract-check report includes: (1) file and line, (2) what's wrong, (3) what the spec says it should be. The agent doesn't need to understand the app -- it applies the diff between actual and spec.

## Deferred Items

- Error injection: merge conflict scenarios (harder to control with worktrees)
- Error injection: missing file scenarios (caught by ownership gate)
- Auto-detect swarm suitability in `/workflows:plan`
- Test agent that auto-generates tests from shared spec
- Backport createDb/createTestDb to Node spec template
- 6+ agent build (further scale)

## Prompt for Next Session

```
Read HANDOFF.md for context. This is sandbox, a compound engineering automation lab.
Build #9 (error injection) completed -- pipeline recovery validated.
Pick next: (A) merge conflict injection, (B) 6+ agent build, (C) auto-detect swarm,
(D) backport Node patterns, (E) test-gen agent, or (F) new experiment.
```
