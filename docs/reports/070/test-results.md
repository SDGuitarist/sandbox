STATUS: PASS

# Test Suite Results — Run 070

## Result: 10/10 PASS

All 10 critical-flow tests passed after one inline fix round to database.py and tests/test_critical_flows.py.

## Fixes Applied

### Fix 1: database.py — :memory: shared connection (also applied for smoke test)
Root cause: SQLite `:memory:` databases are per-connection. The original `init_db()` created
a separate connection, seeded it, then closed it. Each subsequent `get_db()` created a new
`:memory:` connection with no tables.
Fix: For `:memory:` DATABASE config, create ONE persistent connection at init_app() time,
store it in `app.config['_MEMORY_DB']`, and return it from `get_db()` for all requests.
close_db() skips closing it. Production (file-based) databases unaffected.

### Fix 2: test_critical_flows.py — DOOD grid non-shoot-dates
Root cause: Test asserted `lead_days[dates[1]] == "H"` and `lead_days[dates[3]] == "H"`
but dates[1] and dates[3] had no schedule entries — they are NOT in the DOOD grid's
`shoot_dates` (spec: SELECT DISTINCT shoot_date FROM schedule_entries). Only actual
shoot dates appear as keys in the grid.
Fix: Removed assertions for non-shoot-dates (days 2 and 4), keeping assertions for
the 3 actual shoot dates.

### Fix 3: test_critical_flows.py — Budget tests needed project total_budget_cents > 0
Root cause: Seeded project has `total_budget_cents=0`. `allocate_budget` enforces
SUM(allocations) <= total_budget, so any allocation > 0 returned False.
Fix: Added `UPDATE projects SET total_budget_cents = 100000` before allocating in
both test_budget_overspend_rejection and test_expense_delete_restores_spent_cents.

### Fix 4: test_critical_flows.py — create_expense returns None not raises on overspend
Root cause: Test used `pytest.raises(Exception)` but spec Transaction Contracts say
`create_expense` returns None (not raises) on overspend.
Fix: Changed to `assert result is None`.

## Tests

| Test | Result |
|---|---|
| test_call_sheet_generation_end_to_end | PASS |
| test_dood_grid_accuracy | PASS |
| test_budget_overspend_rejection | PASS |
| test_expense_delete_restores_spent_cents | PASS |
| test_department_head_cannot_post_expense_for_other_department | PASS |
| test_crew_member_cannot_view_budget | PASS |
| test_schedule_reorder_rejects_foreign_ids | PASS |
| test_fts5_search_sanitizes_operators | PASS |
| test_reorder_without_csrf_token_is_rejected | PASS |
| test_csp_allows_sortablejs_cdn | PASS |
