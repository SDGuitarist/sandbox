# HANDOFF -- Sandbox

**Date:** 2026-04-12
**Branch:** master
**Phase:** Build #7 complete -- Node/Express swarm validated

## Current State

Notes API (Node/Express + SQLite) built via 3-agent swarm. 11 files, 836 LOC,
45 tests passing, all 13 endpoints verified. This was the first non-Flask swarm
build -- validates the stack-agnostic claim. Two minor review fixes applied
(tag existence check, BigInt cast).

### Build History

| # | App | Type | Stack | Agents | Files | Tests | Result |
|---|-----|------|-------|--------|-------|-------|--------|
| 1 | habit-tracker | solo | Python | 1 | 1 | — | PASS |
| 2 | task-tracker | swarm | Flask | 4 | 19 | — | PASS |
| 3 | bookmark-manager | swarm | Flask | 3 | 17 | — | PASS |
| 4 | recipe-organizer | swarm | Flask | 3 | 24 | — | PASS |
| 5 | finance-tracker | swarm | Flask | 3 | 23 | — | PASS |
| 6 | contact-book | swarm | Flask | 3 | 11 | — | PASS |
| 7 | notes-api | swarm | Node/Express | 3 | 11 | 45 | PASS |

### Pipeline Components

| Component | Location | Status |
|-----------|----------|--------|
| Autopilot skill | .claude/skills/autopilot/SKILL.md | Working (Flask + Node) |
| Flask spec template | docs/templates/shared-spec-flask.md | Working |
| Node spec template | docs/templates/shared-spec-node.md | Battle-tested (build #7) |
| 6 agents | .claude/agents/*.md | Working |
| Solution docs | docs/solutions/ (28 total) | Growing |

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | docs/brainstorms/2026-04-12-notes-api-brainstorm.md |
| Plan | docs/plans/2026-04-12-feat-notes-api-with-tags-plan.md |
| Solution | docs/solutions/2026-04-12-notes-api-node-express-swarm-build.md |
| Reports | docs/reports/028/ |

## Deferred Items

- 5+ agent swarm build (scale test)
- Error injection testing (deliberate merge conflicts, smoke test failures)
- Auto-detect swarm suitability in `/workflows:plan`
- Test agent that auto-generates tests from shared spec
- Backport createDb/createTestDb pattern to Node spec template
- Archive sandbox-auto

## Feed-Forward

- **Hardest decision:** How to handle test DB isolation in Node -- chose
  `createApp(db)` with mandatory db arg and `req.app.locals.db` access.
- **Rejected alternatives:** Environment variable override (fragile), Jest
  module mocking (brittle), global setup/teardown (shared state).
- **Least confident:** Whether the pattern scales to 5+ agents. 3 agents
  worked cleanly but more agents means more cross-reads from shared tables.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is sandbox, a compound engineering automation lab.
Build #7 (notes-api, Node/Express) completed -- stack-agnostic swarm validated.
Pick next: (A) 5-agent swarm to test scale, (B) error injection testing,
(C) backport Node patterns to spec template, or (D) new experiment.
Key files: .claude/skills/autopilot/SKILL.md, docs/templates/shared-spec-node.md
```
