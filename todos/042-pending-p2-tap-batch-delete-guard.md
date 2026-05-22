---
status: pending
priority: p2
issue_id: "042"
tags: [code-review, data-integrity, brewops]
---

# Tap With Assigned Batch Can Be Deleted Silently

## Problem Statement
`delete_tap` catches IntegrityError from sales FK, but if a tap has a batch assigned with zero sales yet, deletion succeeds. The batch is left in 'tapped' status with no tap pointing to it -- an inconsistent state.

Similarly, deleting a tank with `current_batch_id` set leaves the batch in 'brewing' status without a tank.

## Findings
- Data-integrity reviewer: M3 (tap), C2 (tank)

## Proposed Solution
Add pre-delete guards:
- `tap_routes.py`: Check `tap['batch_id'] is not None` before deletion
- `tank_routes.py`: Check `tank['current_batch_id'] is not None` before deletion

## Affected Files
- `app/routes/tap_routes.py` lines 107-123
- `app/routes/tank_routes.py` lines 130-140

## Acceptance Criteria
- [ ] Cannot delete a tap with an active batch assigned
- [ ] Cannot delete a tank with an active batch assigned
