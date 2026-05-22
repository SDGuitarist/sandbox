---
status: pending
priority: p2
issue_id: "041"
tags: [code-review, python-quality, brewops]
---

# dollars Filter Crashes on None Input

## Problem Statement
`app/filters.py` `dollars()` does `cents / 100` with no guard against None. If a template renders `{{ value | dollars }}` where value is None, it crashes with TypeError. The `format_date` filter in the same file handles None gracefully.

## Findings
- Python reviewer: P1-4

## Proposed Solution
```python
def dollars(cents: int | float | None) -> str:
    if cents is None:
        return '$0.00'
    return f'${cents / 100:.2f}'
```

## Affected Files
- `app/filters.py` lines 1-3

## Acceptance Criteria
- [ ] `dollars(None)` returns '$0.00' instead of crashing
