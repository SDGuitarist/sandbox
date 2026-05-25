# Review Context — CPAA Shadow Lab

## Risk Chain

**Brainstorm risk:** "Phase 0 is logical-time only — it proves state derivation from complete history but does NOT test arrival-order bugs, burst handling, or real-time edge conditions."

**Plan mitigation:** Explicitly scoped Phase 0 as logical-time replay. Removed "delayed event" injection that couldn't actually be tested with pre-loaded data. Deferred arrival-order testing to Phase 1.

**Work risk (from Feed-Forward):** "Whether absence-detection via query-time computation (heartbeat staleness, auction stall) will perform acceptably when the dashboard is polling every 500ms at 10x speed."

**Review resolution:** Ultrareview clean — 0 bugs found in cpaa-shadow-lab code. Absence-detection verified <1ms at 1,595 events. Performance risk accepted for Phase 0, deferred optimization to Phase 1.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| app/models/events.py | 8 projection handlers, rebuild/advance, alert merging | Double-counting on rebuild, station name loss |
| app/replay.py | Thread-safe replay clock, 3-state machine | Race conditions between poll and control endpoints |
| app/blueprints/dashboard/routes.py | 6 API endpoints, projection wiring | Concurrent advance + rebuild on same DB connection |
| app/__init__.py | Flask factory, static_folder, CSP | CWD-dependent path resolution |
| static/js/replay.js | Polling, controls, timeline rendering | isDragging guard, filter state, DOM updates |

## Plan Reference

`docs/plans/2026-05-24-feat-cpaa-shadow-lab-event-replay-simulator-plan.md`
