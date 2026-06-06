---
review_agents:
  - learnings-researcher
  - security-sentinel
  - performance-oracle
  - flow-trace-reviewer
---

# Review Context — Sandbox (Gig Outcome Tracker, Run 068)

## Risk Chain

**Brainstorm risk:** Dashboard aggregation query correctness — paid-only revenue / GROUP BY / COALESCE logic. No prior solution doc covers it. The deterministic fixture (3 played, $880, 4.5 avg energy, 8000 tips) is the verification anchor.

**Plan mitigation:** Section 12 prescribed the exact SQL for all dashboard queries (COALESCE, LEFT JOIN, payment_status filter). Deterministic fixture included in Acceptance Tests (Section 14) as a smoke test anchor.

**Work risk (from Feed-Forward):** Whether the dashboard agent would implement the LEFT JOIN correctly (so paid gigs without outcomes still count their pay), apply payment_status='paid' filter (so Gig 3's unpaid $450 is excluded), and average energy over outcome rows (2) not gig rows (3).

**Review resolution:** 0 P1, 2 P2 from 1 review round. Dashboard aggregation verified correct — risk did NOT materialize. Prescriptive SQL in spec was the load-bearing mitigation. P2-1: monthly_revenue months parameter ignored (hardcoded -6). P2-2: init_debrief_schema nested with conn: inconsistency. Both fixed in commit 89c2148. 2 P3s deferred (informational flash category, list_contacts missing ORDER BY).

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| app/gig_models.py | monthly_revenue: parameterize months in SQL | Parameter contract correctness |
| app/debrief_models.py | init_debrief_schema: remove nested with conn: | Transaction consistency with other init_*_schema functions |
| app/dashboard_routes.py | New — dashboard aggregation | COALESCE + LEFT JOIN + payment filter correctness |
| app/__init__.py | New — scaffold, get_db, init_db, auth blueprint | PRAGMA foreign_keys, row_factory placement, SECRET_KEY fail-close |
| app/contact_models.py | Assembly inline fix: executescript → execute | Transaction isolation during init_db |

## Plan Reference

`docs/plans/2026-06-05-gig-outcome-tracker-plan.md`
