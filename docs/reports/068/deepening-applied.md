STATUS: PASS

# Deepening Applied — Run 068

**Plan:** docs/plans/2026-06-05-gig-outcome-tracker-plan.md

## Corrections Applied

| # | Section | Change | Rationale |
|---|---------|--------|-----------|
| 1 | Section 7 — Coordinated Behaviors (get_db / init_db connection path) | Added an explicit "init_db / PRAGMA foreign_keys — per-connection requirement (FC40 extension)" sub-rule under the get_db rule. Specifies that create_app MUST ensure the connection passed to init_db also runs `PRAGMA foreign_keys = ON`, either via get_db() inside an app context or by executing the PRAGMA explicitly on any standalone sqlite3.connect call before DDL. | FC40 — if init_db/seed runs with FK enforcement OFF, all RESTRICT/SET NULL delete behavior the spec depends on is silently unenforced. Highest-severity correction. |
| 2 | Section 6 — Input Validation Prescriptions (gig delete row) | Replaced the `POST /gigs/<id>/delete` validation entry to explicitly require that the route calls `get_outcome_by_gig_id(conn, id) is None` AND `get_debrief_by_gig_id(conn, id) is None` BEFORE calling `delete_gig`. The sqlite3.IntegrityError from FK RESTRICT is now noted as "only the backstop." | Delete-rule discipline — without prescribing the outcome/debrief pre-checks, isolated Agent 5 may rely on RESTRICT alone and surface a raw IntegrityError instead of the friendly status guard. |
| 3 | Section 6 — Input Validation Prescriptions (outcome edit rows) | Added two new rows for `POST /outcomes/<gig_id>/edit`: `tips_cents` (if provided, integer >= 0 → Flash "Tips cannot be negative") and `leads_generated` (if provided, integer >= 0 → Flash "Leads cannot be negative"), matching the create-path checks. | FC43 defense-in-depth — the edit path omitted the non-negative route checks present on create, leaving only the DDL CHECK (raw IntegrityError) as the guard. |
| 4 | Section 8 — Transaction Contracts (set_gig_status error handling) | Replaced the set_gig_status error-handling cell to clarify that the gigs.status CHECK only constrains the allowed value set, NOT the transition direction. An invalid transition (e.g. played→upcoming) passes the CHECK and raises NO IntegrityError. The route MUST validate the transition before calling set_gig_status and flash "Invalid status transition" itself. The misleading "IntegrityError → flash Invalid status transition" note was removed. | Correctness — the described IntegrityError backstop will never fire for a bad transition; it misleads isolated Agent 5 into omitting the required route-level transition guard. |
| 5 | Section 4 / Section 10 — Route declaration order | Strengthened the route-ordering note to be explicitly BINDING on Agent 9 (contact_routes) and Agent 11 (debrief_routes). Replaced the prose advisory with a numbered declaration order requirement: Agent 9 must declare follow-ups, then new, then <id>; Agent 11 must declare search before <gig_id>. Added explicit consequence: other orderings cause Flask to match the converter and return 404 on static routes. | Route-shadowing hazard — the spec mentioned ordering in prose; making it binding on the two affected agents prevents a latent 404 at swarm scale. |

## Unapplied (if any)

| Section | Reason |
|---------|--------|
