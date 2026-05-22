---
status: pending
priority: p2
issue_id: "040"
tags: [code-review, performance, brewops]
---

# No Pagination on Sales List View

## Problem Statement
`get_all_sales()` loads every sale ever recorded with `.fetchall()` and no LIMIT/OFFSET. At 100 sales/day, this is 36,500 rows/year. After 3 years (~110K rows), the page will take multiple seconds and consume significant memory. Other entity tables (taps, tanks, ingredients) are naturally bounded by physical brewery constraints and don't need pagination.

## Findings
- Performance reviewer: CRITICAL-2

## Proposed Solution
Add `LIMIT ? OFFSET ?` parameters to `get_all_sales()` with a COUNT query for pagination controls.

## Affected Files
- `app/models/sale_models.py` (add pagination params)
- `app/routes/sale_routes.py` (pass page param)
- `app/templates/sales/list.html` (add pagination controls)

## Acceptance Criteria
- [ ] Sales list paginates with configurable page size (default 50)
