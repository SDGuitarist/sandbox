---
status: pending
priority: p2
issue_id: "016"
tags: [code-review, security, finance-tracker, validation]
dependencies: ["015"]
unblocks: []
sub_priority: 1
---

# 016 - validate_year_month allows absurd year ranges

## Problem Statement

`validate_year_month` in `utils.py` accepts any year from 0000 to 9999. While not a security risk, it produces nonsensical queries.

## Findings

- **File:** `finance-tracker/app/utils.py`, lines 29-37
- **Agent:** security-sentinel

## Proposed Solutions

Add year range check: `if year < 2000 or year > 2100: raise ValueError("Year out of range")`

- Effort: Small
- Risk: None

## Acceptance Criteria

- [ ] `validate_year_month("0000-01")` raises ValueError
- [ ] `validate_year_month("2026-04")` passes

## Work Log

- 2026-04-09: Created from code review
