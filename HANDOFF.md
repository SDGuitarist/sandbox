# HANDOFF -- Sandbox

**Date:** 2026-05-21
**Branch:** master
**Phase:** Spec completeness checker -- compound phase complete (solution doc + learnings propagated)

## Current State

Spec-completeness-checker fully implemented and reviewed. New pre-swarm gate (Step 9w.6) checks 6 coverage surfaces before swarm launch. 1 P1 + 5 P2 review findings fixed. Solution doc written, learnings propagated. First real build will validate the gate.

## Key Artifacts

| Artifact | Location |
|----------|----------|
| Brainstorm (2 refinement passes) | docs/brainstorms/2026-05-21-spec-completeness-checker-brainstorm.md |
| Plan (3 Codex rounds, 14 fixes) | docs/plans/2026-05-21-feat-spec-completeness-checker-plan.md |
| Solution doc | docs/solutions/2026-05-21-spec-completeness-checker-pre-swarm-gate.md |
| Agent file | .claude/agents/spec-completeness-checker.md |
| Autopilot step | .claude/skills/autopilot/SKILL.md (Step 9w.6) |
| CLAUDE.md sections | CLAUDE.md (Mandatory Spec Coverage Sections) |

## Deferred Items

### Spec Completeness Checker
- P2-D1: Flask spec template missing mandatory section scaffolds -- separate task
- P2-D2: N/A flow repeated 6 times in agent file -- simplicity improvement
- P2-D3: Route-path column detection over-specified -- cosmetic
- Phase 2: Add FC9 (form fields), FC38 (CSP/CDN), FC40 (SQLite PRAGMAs), worker/background coverage

### RestaurantOps (run 052)
- 16 P2s deferred (see prior HANDOFF for full list)

### Prior
- GigSheet 050 P2s, context optimization P2s

## Three Questions

1. **Hardest decision?** Hard FAIL vs WARN. A WARN-only gate never blocks but gets bypassed. A hard FAIL will fire on the first spec the checker misreads. The one-retry-with-commit design mitigates.
2. **What was rejected?** Extending consistency checker (couples concerns), template-only without checker (doesn't prove coverage), all 10 surfaces in v1 (broader than evidence), full markdown parser (fragile).
3. **Least confident about?** Three risks: (1) Route-table column parsing with fixed allowlist, (2) Check 2->1 dependency producing BLOCKED cascade, (3) Heading-prefix matching on future plan formats. First real build validates all three.

## Prompt for Next Session

```
Read HANDOFF.md. This is the Sandbox project.

Two-part session:

PART 1: Scaffold the Flask spec template (manual, ~30 min).
Add the 6 mandatory coverage sections from CLAUDE.md (Mandatory Spec
Coverage Sections) to docs/templates/shared-spec-flask.md as empty
scaffolds with example rows. The sections are:
  1. Export Names Table (Name, Type, Defined By, Used By)
  2. Cross-Boundary Wiring Table (Producer, Consumer, Import Path)
  3. Input Validation Prescriptions (Route, Input, Validation, Error Response)
  4. Coordinated Behaviors (blueprint registration, navbar, flash patterns)
  5. Transaction Contracts (Function, SQL, Commits: yes/no/immediate)
  6. Authorization Matrix (Route, Mode: public/role-only/role+ownership/admin)

Read docs/templates/shared-spec-flask.md first. Add sections with 1-2
example rows each so spec authors know the expected format. Commit when done.

PART 2: Run 053 -- new standalone build to validate the completeness gate.
Gym/fitness center manager. Flask + SQLite + Jinja2. 25+ agent swarm.

Run /autopilot to execute the full compound loop unattended.

The completeness gate (Step 9w.6) will run for the first time on a real
build. Watch for: false positives from heading detection, route-path
column parsing, or Check 2 BLOCKED cascade. Note any issues for
threshold calibration.
```
