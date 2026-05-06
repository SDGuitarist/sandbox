---
status: pending
priority: p3
issue_id: "023"
tags: [code-review, quality, cli]
dependencies: []
---

# leads held shows duplicate count for multi-reason holds

## Problem Statement
`query_held_leads()` uses UNION ALL, so a lead held for multiple reasons (e.g. low_confidence AND no_hook) appears multiple times. The CLI `Total held: N` counts rows, not unique leads.

## Findings
- **Agent**: Data Integrity Guardian
- **Location**: `run.py` line 180, `models.py` lines 38-95
- **Fix**: Use `len(set(h["id"] for h in held))` for unique count, or show both.

## Acceptance Criteria
- [ ] `Total held` shows unique lead count (or both unique + total reasons)

## Work Log
- 2026-05-06: Found by Data Integrity Guardian
