# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/2026-05-13-feat-workshop-registration-hub-plan.md
**Checked:** 2026-05-13 (final re-check after 2 targeted fixes)

## Re-Check Scope

This is a targeted re-check verifying the 2 FAILs from the previous run (N1 and N2) were correctly resolved, confirming no new contradictions were introduced, and re-verifying all previously-PASS and WARN items remain unchanged.

---

## Results

### Part A -- Verification of the 2 Applied Fixes

| # | Fix | Expected | Actual in Plan | Status | Detail |
|---|-----|----------|----------------|--------|--------|
| F1 | `try_promote_next` return type in Export Names Table | `-> None` (matching Shared Interface Spec table) | Line 274: `try_promote_next(conn) -> None` | PASS | Both the main Export Names Table (line 274) and the agent-facing Shared Interface Spec table (line 848) now both read `(conn) -> None`. The conflict is resolved. |
| F2 | Agent 3 brief trigger for `try_promote_next` | "After marking `cancelled` on refund events (`refund.created`), call `try_promote_next(conn)`" | Line 943: exactly that text | PASS | The brief now correctly describes the refund event path: mark `cancelled`, then call `try_promote_next(conn)`. No longer contradicts the state machine transition `paid -> cancelled` on `refund.created`. |

Both previously-FAILed contradictions are confirmed resolved.

---

### Part B -- New Contradictions Introduced by the Fixes

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| -- | (no new contradictions found) | -- | -- | -- | The two fix sites (line 274 and line 943) are each referenced in exactly one other location. Both references are now consistent. No cascading contradictions found. |

---

### Part C -- Carried-Forward Checks (unchanged from prior run)

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| C1 | SQL Type vs Supabase Type | SQLite `registrants.id`: `INTEGER PRIMARY KEY` | Supabase `registrants_realtime.id`: `BIGINT PRIMARY KEY` | WARN | Compatible at runtime (SQLite INTEGER maps to any integer width). Different type names may confuse the agent implementing both schemas. Recommend a comment in schema.sql or supabase schema stating the mapping is intentional. |
| C2 | SQLite TEXT vs Supabase TIMESTAMPTZ | SQLite `created_at`, `paid_at`: `TEXT` (stored as `datetime('now')` with no `Z` suffix) | Supabase `registrants_realtime.created_at`, `paid_at`: `TIMESTAMPTZ` | WARN | `datetime('now')` in SQLite produces strings like `2026-05-14 10:30:00` (no `T`, no `Z`). Supabase may interpret these as local time, not UTC. The sync function (lines 457-464) does not add a `Z` suffix or convert the format before upserting. No explicit handling is prescribed. |
| C3 | Schema Fields vs API Registrant Object | SQLite `registrants` column: `cancelled_at` (line 187) | Registrant object shape in API contract (lines 148-161): `cancelled_at` absent | WARN | Likely intentional -- the API shape omits `cancelled_at`. Not documented as intentional. Agent 2 may or may not serialize this field. |
| C4 | Agent Brief vs Wiring Table (Agent 3) | payment-webhooks agent brief (lines 938-944): no mention of `send_email(registrant_id, "confirmation")` | Wiring Table (line 293): `app/payments/routes.py` (Agent 3) calls `send_email(registrant_id, "confirmation")` | WARN | Agent 3's brief describes status transitions and `try_promote_next` but does not list sending a confirmation email after marking `paid`. The Wiring Table requires it. Agent 3 could miss this step. |
| C5 | Agent Brief vs Wiring Table (Agent 2) | registration-admin-api agent brief (lines 920-924): no mention of `send_email(registrant_id, "waitlist_confirmation")` | Wiring Table (line 306): `app/registration/routes.py` (Agent 2) calls `send_email(registrant_id, "waitlist_confirmation")` | WARN | Agent 2's brief lists 4 key constraints but does not mention sending a waitlist confirmation email when capacity is full and registrant is waitlisted. The Wiring Table requires it. Parallel gap to C4. |
| C6 | Schema vs Route parameter names | All SQLite column names (snake_case) vs all Flask route parameter names | All Flask route handlers | PASS | No camelCase / snake_case mismatch. Consistent throughout. |
| C7 | SQL status values vs state machine | SQL CHECK constraint statuses vs state machine status values vs email template names | All sections | PASS | Five status values (`pending_payment`, `paid`, `waitlisted`, `cancelled`, `payment_failed`) are consistent across the SQL CHECK constraint (lines 181-183), state machine (line 91), endpoint responses, and email template type enum (lines 388-392). |
| C8 | Export Names vs Import References (Flask) | Flask Export Names Table (lines 260-279) | Wiring Table import paths (lines 292-307) and cross-boundary import line (line 865) | PASS | All function names and import paths match exactly across the Export Names Table, Wiring Table, and the canonical cross-boundary import list. |
| C9 | Export Names vs Import References (Express) | Express Export Names Table (lines 283-287) | Agent 7 and Agent 8 briefs | PASS | `createApp`, `flaskProxy`, and `basicAuth` are consistent across all references. |
| C10 | try_promote_next: Export Names Table vs Shared Interface Spec | Line 274: `(conn) -> None` | Line 848: `(conn) -> None` | PASS | **Confirmed resolved by Fix F1.** Both entries now agree on `None` return type. |
| C11 | Route table vs agent handler assignments | Endpoint table (lines 124-131): 6 routes listed | Agent briefs (Agents 1, 2, 3) | PASS | All 6 routes are assigned to a specific agent. `/api/health` -> Agent 1; `/api/register`, `/api/admin/*` -> Agent 2; `/api/webhooks/square` -> Agent 3. No route is listed without a handler assignment and no handler section lacks a route entry. |
| C12 | Cross-boundary wiring completeness | All exported functions in Export Names Table vs declared consumers | Wiring Table + cross-boundary import line | PASS | Every exported function has at least one declared consumer. No orphaned exports. (`update_status` and `get_registrant_by_email` are covered by the cross-boundary import line at 865 even though they lack individual Wiring Table rows -- this is consistent with the spec's approach for direct model-layer functions.) |
| C13 | Mock/Fixture Data vs Schema Fields | N/A -- section not present | N/A | N/A | No mock data fixtures or seed data are included in the spec. |

---

## Findings Detail

### PASS F1 -- try_promote_next return type conflict RESOLVED

The prior FAIL (N1) has been corrected. The main Export Names Table (line 274) previously read `try_promote_next(conn) -> sqlite3.Row | None` while the Shared Interface Spec table (line 848) read `(conn) -> None`. Both now read `-> None`, which is also consistent with the prescribed atomic claim pattern (lines 366-372) where the function returns nothing on success or failure.

### PASS F2 -- payment-webhooks agent brief contradiction RESOLVED

The prior FAIL (N2) has been corrected. Line 943 previously read "After marking `paid`, call `try_promote_next(conn)` only on refund events (`refund.created`)" -- a logically impossible instruction (refund events never mark a registrant `paid`). The line now reads: "After marking `cancelled` on refund events (`refund.created`), call `try_promote_next(conn)` to auto-promote next waitlisted." This aligns with the state machine transition `paid -> cancelled` on `refund.created` and the role of `try_promote_next` in opening a waitlisted spot.

### WARN C4 and C5 -- Agent briefs incomplete relative to Wiring Table

These two WARNs are structurally identical. The Wiring Table is the authoritative cross-module call list, but individual agent briefs do not enumerate every Wiring Table call. An agent reading only its own brief section could miss a required `send_email` call:

- Agent 3 brief omits: `send_email(registrant_id, "confirmation")` after marking `paid`
- Agent 2 brief omits: `send_email(registrant_id, "waitlist_confirmation")` when capacity is full

These are not definite contradictions (the Wiring Table is authoritative and agents are instructed to follow it), but the omission creates a risk that an agent implements the status transition correctly but skips the email. These remain WARNs: a human reviewing agent output should verify these two email calls appear in the generated code.

### WARN C2 -- SQLite datetime format may cause UTC misinterpretation in Supabase

SQLite's `datetime('now')` produces `YYYY-MM-DD HH:MM:SS` format (no `T` separator, no `Z` suffix). Supabase TIMESTAMPTZ columns expect ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`). The sync function (lines 457-464) passes `reg["created_at"]` and `reg["paid_at"]` directly from the SQLite row without format conversion. Supabase's behavior with the bare SQLite format depends on its Postgres driver. This is a runtime risk that cannot be confirmed from the spec alone.

---

## Summary

- **Total checks:** 15 (2 fix verifications + 0 new FAILs + 5 WARNs + 7 PASSes + 1 N/A)
- **PASS:** 9 (2 fix verifications + 7 carried-forward PASSes)
- **FAIL:** 0
- **WARN:** 5 (C1, C2, C3, C4, C5 -- all unchanged from prior run; C5 is a newly-named parallel of C4)
- **N/A (section absent):** 1 (no mock/fixture data)

STATUS: PASS
