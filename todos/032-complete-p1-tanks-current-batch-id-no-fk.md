---
status: pending
priority: p1
issue_id: "032"
tags: [code-review, data-integrity, schema, brewops]
---

# tanks.current_batch_id Has No FK -- Batch Deletion Orphans Tank

## Problem Statement
`tanks.current_batch_id` is declared as `INTEGER UNIQUE` in schema.sql but has no `REFERENCES batches(id)` foreign key constraint. If a batch in 'brewing' status is deleted, the tank's `current_batch_id` still points to the now-deleted batch ID. The tank appears permanently occupied and cannot accept new batches.

The reverse FK (`batches.tank_id REFERENCES tanks(id) ON DELETE SET NULL`) correctly nullifies the batch's tank reference, but leaves the tank's `current_batch_id` pointing at nothing.

## Findings
- Data-integrity reviewer: CRITICAL -- batch deletion with tank_id creates phantom occupancy
- Architecture reviewer: confirmed `current_batch_id` is plain integer, no FK relationship

## Proposed Solutions

### Option A: Add FK with ON DELETE SET NULL (RECOMMENDED)
Change schema to: `current_batch_id INTEGER UNIQUE REFERENCES batches(id) ON DELETE SET NULL`
- Pros: DB automatically clears tank when batch is deleted
- Cons: Requires migration (recreate table or new DB)
- Effort: Small (schema change)

### Option B: Add route-level guard preventing batch deletion when tank assigned
- Pros: No schema change needed
- Cons: Doesn't fix the structural gap, just masks it
- Effort: Small (~5 lines in batch_routes.py)

### Option C: Both A and B (defense in depth)
- Pros: Belt and suspenders
- Effort: Small

## Affected Files
- `schema.sql` line 38 (tanks table definition)
- `app/routes/batch_routes.py` lines 121-137 (delete handler)
- `app/routes/tank_routes.py` lines 130-140 (delete handler -- also needs IntegrityError guard)

## Acceptance Criteria
- [ ] Deleting a batch clears `tanks.current_batch_id` automatically
- [ ] OR deleting a batch with an active tank is prevented with a clear error
