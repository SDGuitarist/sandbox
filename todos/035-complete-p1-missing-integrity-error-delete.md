---
status: pending
priority: p1
issue_id: "035"
tags: [code-review, error-handling, consistency, brewops]
---

# Tank and Staff Delete Routes Missing IntegrityError Guard

## Problem Statement
`tank_routes.py` and `staff_routes.py` delete handlers call `delete_*()` + `conn.commit()` without catching `sqlite3.IntegrityError`. All other delete routes (batch, ingredient, recipe, tap) wrap this pattern in try/except. If FK constraints are violated, users see an unhandled 500 error.

Additionally, `tank_routes.py` should check `tank['current_batch_id'] is not None` before allowing deletion (related to #032).

## Findings
- Python reviewer: P0-2
- Pattern reviewer: Finding A (medium severity)
- Data-integrity reviewer: confirmed gap

## Proposed Solution
Add `try/except sqlite3.IntegrityError` to both delete routes, matching the pattern in batch/ingredient/recipe/tap routes.

## Affected Files
- `app/routes/tank_routes.py` lines 130-140
- `app/routes/staff_routes.py` lines 168-180

## Acceptance Criteria
- [ ] Tank delete handles IntegrityError with flash message
- [ ] Staff delete handles IntegrityError with flash message
- [ ] Consistent delete pattern across all 7 entity routes
