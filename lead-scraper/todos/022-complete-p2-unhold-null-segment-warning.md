---
status: pending
priority: p2
issue_id: "022"
tags: [code-review, quality, cli]
dependencies: []
---

# Warn when unholding a lead with NULL/unsupported segment

## Problem Statement
A user can unhold a lead that has `segment=NULL` or an unsupported segment. The unhold succeeds, but the lead still won't be assigned to campaigns because `assign_leads()` requires `segment IN (available templates)`. The user gets no feedback about why the lead doesn't appear in campaigns after unholding.

## Findings
- **Agents**: Kieran Python Reviewer, Security Sentinel
- **Location**: `run.py` lines 183-208 (`_cmd_leads_unhold`)
- **Evidence**: M1 in security review -- manually approved lead with hook_text=None generates "Alice, None" in messages. NULL segment silently excluded from assignment.

## Proposed Solutions

### Option A: Print warning after unhold (Recommended)
Check the lead's segment against available templates. If missing or unsupported, print a yellow warning:
```
Approved lead 42 (Alice). Was held for: no_hook.
WARNING: Lead has no segment -- will not be assigned to campaigns until enriched.
```
- Effort: Small (5 min)
- Risk: None

## Acceptance Criteria
- [ ] Unholding a lead with NULL segment prints a warning
- [ ] Unholding a lead with unsupported segment prints a warning
- [ ] Unholding a lead with valid segment prints no warning

## Work Log
- 2026-05-06: Found by Kieran Python Reviewer + Security Sentinel
