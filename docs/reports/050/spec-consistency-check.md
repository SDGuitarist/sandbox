# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/2026-05-20-gigsheet-plan.md
**Checked:** 2026-05-20
**Run ID:** 050

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Export Names vs Worker Code | Export Names Table: `increment_campaign_counter` used by `delivery-webhooks (16)` only (line 1743) | Worker code `process_one_job()` calls `increment_campaign_counter` for both sent and failed (lines 1477, 1480) | FAIL | email-queue (26) calls `increment_campaign_counter` but it is not declared as a consumer in the Export Names Table. Agents implementing email-queue (26) will see a contract that forbids this call. |
| 2 | Export Names vs Wiring Table | Export Names Table: `increment_campaign_counter` used by `delivery-webhooks (16)` only | Cross-Boundary Wiring Table entry for email-queue (26) (line 1798) omits `increment_campaign_counter` | FAIL | Same function, two tables, neither acknowledges email-queue (26) as a consumer. Agents implementing delivery-webhooks (16) and email-queue (26) will get conflicting ownership signals. |
| 3 | Transaction Boundary vs Worker Code | Transaction Boundary list: "`complete_job()` in email-queue worker -- each job completion is independent" (line 1923) | Worker `process_one_job()` does NOT call `complete_job()` -- writes raw SQL `UPDATE job_queue SET status = ?, completed_at = ...` directly (lines 1469-1472) | FAIL | The model function `complete_job()` is prescribed as the completion path, but the worker code bypasses it entirely and shadow-writes job_queue directly. This violates the Data Ownership contract and is the exact pattern the plan warns against ("NO shadow SQL"). |
| 4 | Model Function Name vs Worker Function Name | Models section defines `reclaim_timed_out_jobs(conn)` (line 1040) | Worker defines `reclaim_timed_out(conn)` (line 1491) -- different name, equivalent logic | FAIL | Transaction Boundary Annotations reference `reclaim_timed_out_jobs()` as the function that commits. The worker calls a locally-defined `reclaim_timed_out()` instead. The named model function is orphaned (never called). Agents implementing email-queue (26) will see two differently-named functions for the same operation and have no authoritative signal about which to use. |
| 5 | Wiring Table vs Export Names Table | Export Names Table: `get_campaign_progress` used by `campaign-sender (14)` AND `sse-events (29)` (line 1745) | Cross-Boundary Wiring Table entry for campaign-sender (14) (line 1788): `get_campaign, enqueue_send_jobs, update_campaign_status, create_notification` -- `get_campaign_progress` absent | FAIL | Template Render Context (line 1674) confirms campaign-sender (14) passes `progress=get_campaign_progress(...)` to its status template. The Wiring Table omits this. campaign-sender (14) agent has no spec authorization to call this function. |
| 6 | Wiring Table vs Export Names Table | Export Names Table: `update_recipient_status` used by `delivery-webhooks (16)` AND `email-queue (26)` (line 1742) | Cross-Boundary Wiring Table entry for email-queue (26) (line 1798): `render_template_with_lead, update_campaign_progress` -- `update_recipient_status` absent | FAIL | Worker code calls `update_recipient_status(db, recipient['id'], 'sent', message_id)` and `update_recipient_status(db, recipient['id'], 'failed')` (lines 1476, 1479). The Wiring Table omits this cross-boundary call for email-queue (26). |
| 7 | Wiring Table vs Export Names Table | Export Names Table: `remove_workspace_member` used by `workspace-members (25)` (line 1762); `update_member_role` used by `workspace-members (25)` (line 1763) | Cross-Boundary Wiring Table entry for workspace-members (25) (line 1797): `add_workspace_member, get_workspace_members, create_notification` -- both functions absent | WARN | Route `POST /members/<id>/remove` and `POST /members/<id>/role` exist in the route table (lines 1597-1598) and both model functions exist. But the Wiring Table does not authorize workspace-members (25) to call them. Incomplete, not contradictory. |
| 8 | Wiring Table vs Export Names / Template Render Context | Export Names Table: `count_leads_by_workspace` used by `dashboard (1)` (line 1717); `get_campaigns_by_workspace` used by `dashboard (1)` (line 1737); `get_stage_counts` used by `scaffold (1) dashboard` (line 1761) | Cross-Boundary Wiring Table entry for scaffold (1) (line 1802): `get_unread_notifications, mark_notification_read` only | WARN | Template Render Context confirms scaffold/dashboard agent calls all three functions (lines 1615-1618). The Wiring Table entry is severely incomplete for scaffold (1). Agents using the Wiring Table as an authorization gate will see no permission for these calls. |
| 9 | Wiring Table completeness | Export Names Table: `get_templates_by_workspace` used by `template-list (9)` (line 1731) | Cross-Boundary Wiring Table: template-list (9) is entirely absent as a caller | WARN | template-list (9) must call `get_templates_by_workspace` to render its index page but has no Wiring Table entry at all. |
| 10 | Wiring Table completeness | Export Names Table: `get_campaigns_by_workspace` used by `campaign-list (12)` (line 1737) | Cross-Boundary Wiring Table: campaign-list (12) is entirely absent as a caller | WARN | campaign-list (12) must call `get_campaigns_by_workspace` to render its index page but has no Wiring Table entry at all. |
| 11 | Schema field vs SSE payload | `campaign_progress` schema: `delivered INTEGER NOT NULL DEFAULT 0` (line 442); SSE code sends `delivered: progress['delivered']` (line 2153) | No code path in the spec passes a non-zero `delivered_delta` to `update_campaign_progress` -- webhooks agent calls `increment_campaign_counter` for delivered count but never calls `update_campaign_progress` with `delivered_delta` | WARN | The SSE client will always show `delivered: 0`. The `delivered` column in `campaign_progress` is populated from nowhere. Not a contradiction in field names or types, but a design gap that may confuse the email-queue (26) and delivery-webhooks (16) agents. |
| 12 | Export Names Table: get_db attribution | Export Names Table: `get_db` defined by `models (3)` (line 1704) | `get_db` is actually defined in `app/db.py`, not `app/models.py` | WARN | Both files are owned by agent 3 (models), so there is no ownership conflict, but agents importing from `app.models` instead of `app.db` will get an ImportError. The import path matters at implementation time. |

---

## Detailed FAIL Analysis

### FAIL 1+2: `increment_campaign_counter` ownership gap (most critical)

The spec prescribes in `send_worker.py` (lines 1477, 1480):
```python
increment_campaign_counter(db, job_row['campaign_id'], 'sent_count')
increment_campaign_counter(db, job_row['campaign_id'], 'failed_count')
```

But the Export Names Table (line 1743) declares `increment_campaign_counter` is used ONLY by `delivery-webhooks (16)`. The Cross-Boundary Wiring Table (line 1798) entry for email-queue (26) omits it entirely. Both tables must be updated to include `email-queue (26)` as a consumer.

### FAIL 3: Shadow-write violates Data Ownership contract

The spec defines `complete_job(conn, job_id, success, error_message='')` in `app/models.py` (line 1029). The Transaction Boundary Annotations (line 1923) say this function commits. The prescriptive worker code (lines 1469-1472) instead executes raw SQL directly:

```python
db.execute('''
    UPDATE job_queue SET status = ?, completed_at = datetime('now'), error_message = ?
    WHERE id = ?
''', (job_status, error_msg, job_row['id']))
```

This is the exact "shadow SQL" pattern the plan explicitly prohibits (P1 fix #6: "Fixed send_worker.py to use models functions via app context"). The fix was declared but not applied to the code block. The email-queue (26) agent will receive conflicting instructions: the plan says "use models functions, NO shadow SQL" but the code block shows shadow SQL.

### FAIL 4: `reclaim_timed_out_jobs` vs `reclaim_timed_out` name mismatch

Models section defines: `def reclaim_timed_out_jobs(conn) -> int` (line 1040)
Worker defines locally: `def reclaim_timed_out(conn)` (line 1491, different name, no return value)
Transaction Boundary Annotations reference: `reclaim_timed_out_jobs()` (line 1924)

The model function is documented and committed to the models section but is never called by the worker. The worker's local function replicates the SQL without committing (missing `conn.commit()` -- the local version does call `conn.commit()` at line 1505, so logic is equivalent, but the names don't match). The orphaned `reclaim_timed_out_jobs` in models.py will confuse the models agent (3) and the email-queue agent (26).

### FAIL 5: campaign-sender (14) missing `get_campaign_progress` in Wiring Table

The `campaign_sender/status.html` template render context (line 1673) shows:
```python
progress=progress,  # Row from get_campaign_progress (or None)
```

This means campaign-sender (14) must call `get_campaign_progress`. The Export Names Table acknowledges this (line 1745). The Wiring Table does not, leaving campaign-sender (14) agents with no spec authorization for this cross-boundary call.

### FAIL 6: email-queue (26) missing `update_recipient_status` in Wiring Table

Worker code calls `update_recipient_status` on lines 1476 and 1479. Export Names Table (line 1742) acknowledges email-queue (26) as a consumer. Wiring Table (line 1798) omits it.

---

## Summary

- **Total checks:** 12
- **PASS:** 0 (all cross-section checks that were clean were not individually enumerated -- the PASSes are schema field names, PIPELINE_STAGES constant, SQL CHECK constraint values, blueprint names, and blueprint registration code which are all consistent)
- **FAIL:** 6
- **WARN:** 6
- **N/A (section absent):** Mock/Fixture data section -- spec contains no seed data fixtures to check against schema (seed.py is agent 30 but no fixture rows are specified in the plan)

---

## Fix Priority

The 6 FAILs must be resolved before swarm launch. Recommended fixes:

1. **FAIL 1+2:** Add `email-queue (26)` to the "Used By" column for `increment_campaign_counter` in the Export Names Table. Add `increment_campaign_counter` to the email-queue (26) row in the Cross-Boundary Wiring Table.

2. **FAIL 3:** Replace the raw SQL in `process_one_job()` (lines 1469-1472) with a call to `complete_job(db, job_row['id'], success, error_msg)`. Remove the raw UPDATE. The function already exists and commits correctly.

3. **FAIL 4:** Either (a) rename the worker's `reclaim_timed_out` to `reclaim_timed_out_jobs` and make it call the model function, OR (b) remove `reclaim_timed_out_jobs` from `app/models.py` and declare `reclaim_timed_out` as the authoritative function in the worker only. Choose one and make all three sections consistent.

4. **FAIL 5:** Add `get_campaign_progress` to the campaign-sender (14) row in the Cross-Boundary Wiring Table.

5. **FAIL 6:** Add `update_recipient_status` to the email-queue (26) row in the Cross-Boundary Wiring Table.

---

STATUS: FAIL -- 6 contradictions found
