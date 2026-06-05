Read docs/plans/2026-05-24-feat-cpaa-shadow-lab-event-replay-simulator-plan.md.

Codex verification pass is close, but the plan is not clean yet. No new P0s were introduced, but there are still two required fixes and one optional alignment cleanup before moving to `/workflows:work`.

Required fixes:

1. Fix the alert resolution contract.
   - The revised alert model correctly switched materialized alerts to a stable `alert_key` primary key.
   - But the event taxonomy still defines:
     - `system.alert.resolved -- { alert_id, reason }`
   - That no longer matches the materialized alert design.
   - Update the plan so resolution uses `alert_key` consistently everywhere the contract is described.
   - Make sure the projection handler description, event taxonomy, examples, and any acceptance language all agree on `alert_key`, not `alert_id`.

2. Scrub stale out-of-order/arrival-order claims from the plan.
   - The plan now correctly scopes Phase 0 as logical-time-only replay and removes the delayed-arrival failure injection.
   - But stale language still claims Phase 0 is testing out-of-order events / out-of-order arrivals in a few places.
   - Clean up these sections so they consistently reflect the new scope:
     - Overview
     - Problem Statement
     - Any state-lifecycle risk text that still talks about earlier-than-cursor events in Phase 0
     - Plan Quality Gate / “most likely way this plan is wrong”
   - The revised truth should be:
     - Phase 0 proves logical-time state derivation from complete history.
     - It does NOT test arrival-order ambiguity, buffered bursts, or real-time edge conditions.
     - Those move to Phase 1+.

Optional but recommended cleanup:

3. Acknowledge the brainstorm/plan narrowing around `chain_id`.
   - The brainstorm MVP still mentions a causal chain ID in the event log scope.
   - The plan removed `chain_id` as YAGNI for Phase 0.
   - That simplification is reasonable, but note it explicitly somewhere if you want strict phase-doc alignment and to avoid the appearance of accidental drift.

Verification summary from Codex:

- `RESOLVED`: projection cursor is now correctly centralized in `replay_meta.last_projected_time`
- `PARTIAL`: alert model is correct structurally, but the `alert_id` → `alert_key` contract rename is incomplete
- `PARTIAL`: failure-injection semantics are correctly narrowed, but stale out-of-order wording remains
- `RESOLVED`: replay state machine transitions and acceptance tests are now aligned
- `RESOLVED`: API/timeline cleanup and failure-count cleanup landed correctly

After applying the fixes:

1. Re-review the plan against the brainstorm and confirm there are no remaining stale references to out-of-order testing in Phase 0.
2. Report any remaining risks before the task is considered complete.
