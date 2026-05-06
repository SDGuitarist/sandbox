---
status: pending
priority: p2
issue_id: "019"
tags: [code-review, architecture, quality]
dependencies: []
---

# Extract MAX_CONSECUTIVE_FAILS as module constant

## Problem Statement
The hardcoded `3` for the circuit breaker threshold appears in 3 separate enrichment loops. If the threshold needs to change, all 3 must be updated. Cross-agent consensus (Architecture + Simplicity + Python reviewers) flags this as copy-paste drift risk.

## Findings
- **Agents**: Architecture Strategist, Code Simplicity Reviewer, Kieran Python Reviewer
- **Location**: `enrich.py` lines 201, 544, 1163
- **Evidence**: Same `consecutive_fails >= 3` pattern in `enrich_leads`, `enrich_with_hunter`, `enrich_hook`

## Proposed Solutions

### Option A: Module-level constant (Recommended)
Add `MAX_CONSECUTIVE_FAILS = 3` at the top of `enrich.py`. Reference in all 3 loops.
- Pros: 1-line addition + 3 substitutions. Clear, searchable, single point of change.
- Cons: None
- Effort: Small (2 min)
- Risk: None

## Acceptance Criteria
- [ ] `MAX_CONSECUTIVE_FAILS` defined at module level in `enrich.py`
- [ ] All 3 loops reference the constant, not the literal `3`
- [ ] All tests pass

## Work Log
- 2026-05-06: Flagged by 3 agents during review
