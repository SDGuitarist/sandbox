---
status: pending
priority: p1
issue_id: "031"
tags: [code-review, data-integrity, derived-state, brewops]
---

# Manual tapped->empty Transition Permanently Locks Tap

## Problem Statement
`VALID_TRANSITIONS['tapped'] = ['empty']` allows advancing a tapped batch to empty via the batch advance route. But `advance_batch_status()` only clears the tank on 'ready' -- it has no branch to clear `taps.batch_id` on 'empty'. Only `create_sale()` (sale_models.py:96-98) clears the tap when a batch empties naturally through sales.

Result: if an admin manually advances a tapped batch to 'empty', the tap retains `batch_id` pointing to a now-empty batch. With `taps.batch_id UNIQUE`, no new batch can be assigned to that tap. The tap is permanently locked.

## Findings
- Flow-trace reviewer: P1 -- traced 3-file chain (batch_models VALID_TRANSITIONS -> advance_batch_status -> schema taps.batch_id UNIQUE)
- Data-integrity reviewer: confirmed tap becomes unrecoverable when sales exist (ON DELETE RESTRICT)
- Plan's Derived State table says `batches.status -> 'empty'` is owned by `sale_models / create_sale()`

## Proposed Solutions

### Option A: Remove 'empty' from VALID_TRANSITIONS['tapped'] (RECOMMENDED)
- Pros: Zero code added, matches derived state ownership (create_sale owns the empty transition)
- Cons: Admin loses ability to manually mark a tapped batch as empty
- Effort: Small (1 line change)

### Option B: Add tap-clear logic to advance_batch_status for 'empty'
- Pros: Admin retains manual control
- Cons: Duplicates logic from create_sale, two code paths for the same state transition
- Effort: Small (~5 lines)

## Affected Files
- `app/models/batch_models.py` lines 4-12 (VALID_TRANSITIONS), lines 163-170 (advance_batch_status)
- `app/models/sale_models.py` lines 92-98 (create_sale tap-clear logic)

## Acceptance Criteria
- [ ] Advancing a tapped batch does not leave taps in an inconsistent state
- [ ] Tap can always be reassigned after its batch is emptied
