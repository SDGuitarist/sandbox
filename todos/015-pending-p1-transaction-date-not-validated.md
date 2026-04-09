---
status: pending
priority: p1
issue_id: "015"
tags: [code-review, security, finance-tracker, validation]
dependencies: []
unblocks: ["016"]
sub_priority: 1
---

# 015 - Transaction date not validated server-side

## Problem Statement

`transaction_date` from form input is passed directly to the database with no format validation. While parameterized queries prevent SQL injection, malformed dates corrupt data integrity and break date-range filtering in dashboard and transaction list queries.

## Findings

- **File:** `finance-tracker/app/blueprints/transactions/routes.py`, lines 75 and 127
- **Agent:** security-sentinel
- `transaction_date = request.form.get("transaction_date", "").strip()` -- no format check
- Any string gets stored, breaking `get_transactions` date-range comparisons

## Proposed Solutions

### Option A: Regex + strptime validation (Recommended)
```python
import re
from datetime import datetime
date_str = request.form.get("transaction_date", "").strip()
if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
    flash("Invalid date format.", "error")
    return rerender()
try:
    datetime.strptime(date_str, "%Y-%m-%d")
except ValueError:
    flash("Invalid date.", "error")
    return rerender()
```
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] Submitting "not-a-date" as transaction_date flashes error and re-renders form
- [ ] Submitting "2026-02-30" (invalid date) flashes error
- [ ] Valid dates like "2026-04-09" still work

## Work Log

- 2026-04-09: Created from code review (security-sentinel agent)
