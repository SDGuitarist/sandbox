STATUS: PASS

# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/2026-06-05-gig-outcome-tracker-plan.md
**Checked:** 2026-06-05 (commit 30c0b3b — final re-run, complete cross-section pass)

## Results

| # | Category | Left Side (Section 4 "Used By") | Right Side (Section 5 wiring rows) | Status | Detail |
|---|----------|---------------------------------|-------------------------------------|--------|--------|
| 1 | Export vs Wiring | create_venue → venue_routes | venue_routes → create_venue | PASS | |
| 2 | Export vs Wiring | get_venue → venue_routes, gig_routes, contact_routes | all three wiring rows present | PASS | |
| 3 | Export vs Wiring | list_venues → venue_routes, gig_routes, contact_routes | all three wiring rows present | PASS | commit 30c0b3b resolved prior FAIL |
| 4 | Export vs Wiring | update_venue → venue_routes | venue_routes → update_venue | PASS | |
| 5 | Export vs Wiring | delete_venue → venue_routes | venue_routes → delete_venue | PASS | |
| 6 | Export vs Wiring | venue_name_exists → venue_routes | venue_routes → venue_name_exists | PASS | |
| 7 | Export vs Wiring | create_gig → gig_routes | gig_routes → create_gig | PASS | |
| 8 | Export vs Wiring | get_gig → gig_routes, outcome_routes, debrief_routes, contact_routes | all four wiring rows present | PASS | |
| 9 | Export vs Wiring | list_gigs → gig_routes, contact_routes | both wiring rows present | PASS | commit b30f7e3 resolved prior FAIL |
| 10 | Export vs Wiring | update_gig → gig_routes | gig_routes → update_gig | PASS | |
| 11 | Export vs Wiring | delete_gig → gig_routes | gig_routes → delete_gig | PASS | commit b30f7e3 resolved prior FAIL |
| 12 | Export vs Wiring | set_gig_status → gig_routes | gig_routes → set_gig_status | PASS | |
| 13 | Export vs Wiring | count_gigs_by_venue → venue_routes | venue_routes → count_gigs_by_venue | PASS | |
| 14 | Export vs Wiring | list_gigs_by_venue → venue_routes | venue_routes → list_gigs_by_venue | PASS | |
| 15 | Export vs Wiring | count_played_gigs → dashboard | dashboard_routes → count_played_gigs | PASS | "dashboard" in Sec 4 = "dashboard_routes" module; consistent throughout |
| 16 | Export vs Wiring | total_revenue_cents → dashboard | dashboard_routes → total_revenue_cents | PASS | |
| 17 | Export vs Wiring | top_venues → dashboard | dashboard_routes → top_venues | PASS | |
| 18 | Export vs Wiring | recent_gigs → dashboard | dashboard_routes → recent_gigs | PASS | |
| 19 | Export vs Wiring | monthly_revenue → dashboard | dashboard_routes → monthly_revenue | PASS | |
| 20 | Export vs Wiring | create_outcome → outcome_routes | outcome_routes → create_outcome | PASS | |
| 21 | Export vs Wiring | get_outcome_by_gig_id → outcome_routes, gig_routes | both wiring rows present | PASS | commit b30f7e3 resolved prior FAIL |
| 22 | Export vs Wiring | update_outcome → outcome_routes | outcome_routes → update_outcome | PASS | |
| 23 | Export vs Wiring | avg_energy_by_venue → venue_routes | venue_routes → avg_energy_by_venue | PASS | |
| 24 | Export vs Wiring | avg_audience_energy → dashboard | dashboard_routes → avg_audience_energy | PASS | |
| 25 | Export vs Wiring | total_tips_cents → dashboard | dashboard_routes → total_tips_cents | PASS | |
| 26 | Export vs Wiring | create_contact → contact_routes | contact_routes → create_contact | PASS | |
| 27 | Export vs Wiring | get_contact → contact_routes | contact_routes → get_contact | PASS | |
| 28 | Export vs Wiring | list_contacts → contact_routes | contact_routes → list_contacts | PASS | |
| 29 | Export vs Wiring | update_contact → contact_routes | contact_routes → update_contact | PASS | |
| 30 | Export vs Wiring | delete_contact → contact_routes | contact_routes → delete_contact | PASS | |
| 31 | Export vs Wiring | list_follow_ups → contact_routes | contact_routes → list_follow_ups | PASS | |
| 32 | Export vs Wiring | list_contacts_by_gig_id → gig_routes | gig_routes → list_contacts_by_gig_id | PASS | |
| 33 | Export vs Wiring | create_debrief → debrief_routes | debrief_routes → create_debrief | PASS | |
| 34 | Export vs Wiring | get_debrief_by_gig_id → debrief_routes, gig_routes | both wiring rows present | PASS | commit b30f7e3 resolved prior FAIL |
| 35 | Export vs Wiring | update_debrief → debrief_routes | debrief_routes → update_debrief | PASS | |
| 36 | Export vs Wiring | search_debriefs → debrief_routes | debrief_routes → search_debriefs | PASS | |
| 37 | Wiring Completeness | No orphan Section 5 rows (rows with no Section 4 backing) | — | PASS | Every Section 5 consumer/function pair has a matching Section 4 Used By entry |
| 38 | Schema vs Route Params | SQL snake_case ids (venue_id, gig_id, met_at_gig_id) | Route params <id>, <venue_id>, <gig_id>; function params match | PASS | Consistent snake_case throughout all sections |
| 39 | SQL Types vs App Types | SQL TEXT for all IDs; INTEGER for *_cents, energy, rating, leads, capacity | Function signatures and validation table use str/int matching SQL types | PASS | |
| 40 | Route Methods vs Route Table | Section 4 url_for endpoint table (29 endpoints) | Section 10 route table | PASS | All 29 endpoints in Section 4 appear in Section 10; no orphan routes in either direction |
| 41 | Mock/Fixture vs Schema | Fixture fields: actual_pay_cents, payment_status, audience_energy, tips_cents, overall_rating, status | Section 3 schema columns | PASS | All fixture fields exist in schema with matching types |
| 42 | ON DELETE: delete_venue | gigs.venue_id ON DELETE RESTRICT; contacts.venue_id ON DELETE SET NULL — MIX | Section 3 Delete Rules + Section 8: route catches sqlite3.IntegrityError | PASS | Catch is correct: RESTRICT child (gigs) can fire IntegrityError |
| 43 | ON DELETE: delete_gig | outcomes.gig_id ON DELETE RESTRICT; debriefs.gig_id ON DELETE RESTRICT; contacts.met_at_gig_id ON DELETE SET NULL — MIX with two RESTRICT children | Section 3 + Section 8: route catches sqlite3.IntegrityError as backstop after pre-check | PASS | Catch is correct: two RESTRICT children can fire IntegrityError |
| 44 | Coordinated Behavior: csrf_token() | Section 7 rule 1: every POST form uses {{ csrf_token() }} with parens | Section 15 agent briefs all reference Section 7 | PASS | |
| 45 | Coordinated Behavior: flash categories | Section 7 rule 8: exactly 'error' and 'success' | Section 6 validation table flash messages | PASS | No third category appears anywhere in the spec |

## Summary

- **Total checks:** 45
- **PASS:** 45
- **FAIL:** 0
- **WARN:** 0
- **N/A (section absent):** 0

## Cross-Section Completeness Notes

All 36 cross-agent model functions in Section 4 have at least one wiring row in Section 5.
All 46 Section 5 wiring rows have a matching Section 4 Used By entry.
Schema init constants (VENUE_SCHEMA, GIG_SCHEMA, etc.) and init_*_schema functions are used
only by the scaffold's init_db at startup and are correctly omitted from the Section 5
runtime wiring table per spec convention. The scaffold exports (get_db, login_required)
are covered by the catch-all "(all routes)" row in Section 5.
