---
status: pending
priority: p2
issue_id: "017"
tags: [code-review, validation, finance-tracker]
dependencies: []
unblocks: []
sub_priority: 2
---

# 017 - Description length not validated in route

## Problem Statement

Transaction description has a DB CHECK(length <= 200) but the route doesn't validate before insert. Over-length descriptions cause unhandled IntegrityError (500 error).

## Findings

- **File:** `finance-tracker/app/blueprints/transactions/routes.py`, line 74
- **Agent:** security-sentinel

## Proposed Solutions

Add `if len(description) > 200: flash("Description too long.", "error"); return rerender()`

- Effort: Small
- Risk: None

## Work Log

- 2026-04-09: Created from code review
