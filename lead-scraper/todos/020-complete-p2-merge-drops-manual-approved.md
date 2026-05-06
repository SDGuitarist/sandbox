---
status: pending
priority: p2
issue_id: "020"
tags: [code-review, data-integrity]
dependencies: []
---

# merge_leads drops manual_approved state

## Problem Statement
The `merge_leads()` function in `models.py` uses `fill_fields` to decide which columns to copy from less-complete duplicates to the keeper. `manual_approved` is not in this list. If a manually approved lead is merged as the less-complete duplicate, the approval is silently lost.

## Findings
- **Agent**: Data Integrity Guardian
- **Location**: `models.py` lines 161-166 (`fill_fields` list)
- **Evidence**: `fill_fields` does not include `manual_approved`. The merge uses COALESCE fill-from-NULL, but `manual_approved` needs MAX/OR semantics (if ANY duplicate was approved, keeper should be approved).

## Proposed Solutions

### Option A: Add special-case merge for manual_approved (Recommended)
After the standard fill, if any duplicate in the group had `manual_approved=1`, set it on the keeper.
- Pros: Preserves the approval intent
- Cons: 5-line addition to merge logic
- Effort: Small
- Risk: Low

### Option B: Add to fill_fields as-is
- Pros: Simpler (1-line change)
- Cons: fill_fields uses COALESCE (fill NULL only), so if keeper already has `manual_approved=0`, it won't be overwritten by a duplicate's `1`. Wrong semantics.

## Acceptance Criteria
- [ ] Merging leads where any duplicate has manual_approved=1 preserves the approval on the keeper
- [ ] Test covers this scenario

## Work Log
- 2026-05-06: Found by Data Integrity Guardian during review
