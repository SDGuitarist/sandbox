# Spec Contract Check -- Run 050

STATUS: FAIL -- 5 mismatches found (1 P0, 3 P1, 1 P2)

## P0: Runtime Crash
- delivery_webhooks/routes.py:117,125 -- queries `user_id` column but schema has `created_by_user_id`

## P1: Data Ownership Violations
- campaign_editor/routes.py:190 -- direct DELETE FROM campaigns (no model function)
- campaign_scheduler/routes.py:34 -- direct UPDATE campaigns SET scheduled_at (no model function)
- workspace_settings/routes.py:43 -- direct UPDATE workspaces SET name (no model function)

## P2: Template Context Mismatch
- lead_import/routes.py:125 -- passes `temp_name` instead of spec's `filename`; missing `total_rows`

## Checks Passed: 114/119
- All 25 blueprints registered correctly
- All 59 model functions present with correct signatures
- All transaction boundaries match spec
- Email chain wiring verified end-to-end
- FC35 ownership checks present on all detail/edit/delete routes
- CSRF exemption + rate limits correct on webhook endpoint

## Fix Attempt

**Errors addressed:** 5
**Files modified:**
- `gigsheet/app/delivery_webhooks/routes.py` -- changed `user_id` to `created_by_user_id` in both the SELECT column list and the dict key reference on lines 117 and 125
- `gigsheet/app/models.py` -- added three new model functions: `delete_campaign`, `update_campaign_schedule`, and `update_workspace` (all do NOT commit)
- `gigsheet/app/campaign_editor/routes.py` -- imported `delete_campaign`; replaced direct `conn.execute('DELETE FROM campaigns ...')` with `delete_campaign(conn, id)`
- `gigsheet/app/campaign_scheduler/routes.py` -- imported `update_campaign_schedule`; replaced direct `conn.execute('UPDATE campaigns SET scheduled_at ...')` with `update_campaign_schedule(conn, id, scheduled_at, timezone)`
- `gigsheet/app/workspace_settings/routes.py` -- imported `update_workspace`; replaced direct `conn.execute('UPDATE workspaces SET name ...')` with `update_workspace(conn, g.workspace['id'], name, from_email, from_name)`
- `gigsheet/app/lead_import/routes.py` -- renamed `temp_name=temp_name` to `filename=temp_name` and added `total_rows=len(preview_rows) + len(error_rows)` in the `render_template` call for `preview.html`

**Fixes applied:**
1. (P0) Corrected wrong column name `user_id` -> `created_by_user_id` in delivery_webhooks SELECT query and dict access -- prevents KeyError runtime crash on bounce/drop events
2. (P1) Added `delete_campaign(conn, campaign_id)` to models.py and called it from campaign_editor delete route -- routes no longer shadow the model layer with raw SQL
3. (P1) Added `update_campaign_schedule(conn, campaign_id, scheduled_at, timezone)` to models.py and called it from campaign_scheduler set_schedule route -- same reason
4. (P1) Added `update_workspace(conn, workspace_id, name, from_email, from_name)` to models.py and called it from workspace_settings update route -- same reason
5. (P2) Renamed `temp_name` context variable to `filename` and added `total_rows` so the preview.html template receives the variable names the spec requires

STATUS: FIXED
