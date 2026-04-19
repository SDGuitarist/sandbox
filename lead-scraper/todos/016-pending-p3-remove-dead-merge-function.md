---
status: pending
priority: p3
issue_id: "016"
tags: [code-review, quality]
---

# Remove Dead _merge_social_handles Function

## Problem Statement
`_merge_social_handles()` merges existing + new social handles with deduplication. But the enrichment queries all filter on `social_handles IS NULL`, and steps run sequentially. Once step 1 writes handles, later steps skip that lead. The merge scenario (two steps finding handles for the same lead) cannot happen with the current code.

## Findings
- **Source:** Simplicity Reviewer
- **File:** `enrich.py` lines 275-282

## Proposed Solution
Remove `_merge_social_handles()`. Replace calls with direct `json.dumps(new_handles)`. If merge is ever needed in the future, add it back.

## Acceptance Criteria
- [ ] Function removed
- [ ] All callers use direct JSON serialization
- [ ] Tests pass
