---
status: pending
priority: p2
issue_id: "021"
tags: [code-review, quality, python]
dependencies: []
---

# Add type hints to new functions

## Problem Statement
Several new/modified functions lack type annotations: `parse_retry_after`, `unhold_lead` (db_path), `query_held_leads` (db_path), CLI handlers. The return type of `parse_retry_after` is inconsistent (int sometimes, float other times).

## Findings
- **Agent**: Kieran Python Reviewer
- **Locations**:
  - `resilience.py:15` -- `parse_retry_after(header_value, fallback=10.0)` missing types
  - `resilience.py:29` -- returns `int` from `min()` but `float` from `fallback`
  - `models.py:38,230` -- `db_path` parameter missing type
  - `run.py:157-183` -- CLI handlers missing types

## Proposed Solutions

### Option A: Add types + normalize return (Recommended)
```python
def parse_retry_after(header_value: str | None, fallback: float = 10.0) -> float:
    ...
    return float(min(max(0, wait), MAX_RETRY_WAIT))
```
Add `db_path: Path = DB_PATH` to models.py functions. Add `-> None` to CLI handlers.
- Effort: Small (10 min)
- Risk: None

## Acceptance Criteria
- [ ] `parse_retry_after` has full type annotations and always returns float
- [ ] `db_path` typed in `query_held_leads` and `unhold_lead`
- [ ] All tests pass

## Work Log
- 2026-05-06: Found by Kieran Python Reviewer
