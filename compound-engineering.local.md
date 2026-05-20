# Review Context -- VenueConnect (Run 049)

## Risk Chain

**Brainstorm risk:** RBAC permission boundaries and booking state machine are the two novel patterns most likely to produce cross-section contradictions in the spec.

**Plan mitigation:** Prescriptive code blocks for advance_booking_state() call pattern embedded in consuming agents' briefs. Spec consistency checker pre-swarm gate.

**Work risk (from Feed-Forward):** Calendar conflict detection atomicity -- BEGIN IMMEDIATE + check_room_available + create_booking must be in same transaction.

**Review resolution:** 8 P1s (5 IDOR, 1 FTS5 injection, 2 unvalidated financial parsing), 9 P2s (3 performance, 6 security). All P1s fixed. State machine had 0 bugs (prescriptive spec). IDOR was #1 finding (prose-described ownership checks).

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| app/settlements/routes.py | Added IDOR ownership checks, try/except on financial parsing | Authorization, input validation |
| app/booking_create/routes.py | Added IDOR check, try/except, percentage validation | Authorization, input validation |
| app/booking_manage/routes.py | Fixed rounding (added round()) | Financial precision |
| app/events/routes.py | Added venue validation on link_booking | Privilege escalation |
| app/models.py | Added FTS5 sanitization, venue_manager_id to settlement query | Injection, authorization |

## Plan Reference

`docs/plans/2026-05-19-venueconnect-plan.md`

## Review Agents

review_agents:
  - security-sentinel
  - performance-oracle
  - flow-trace-reviewer
  - learnings-researcher
