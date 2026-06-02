---
status: pending
priority: p2
issue_id: "051"
tags: [code-review, architecture, testing-routes, run-061]
dependencies: []
---

# Raw SQL in Testing Route Bypassing Model Layer

## Problem Statement

`testing/routes.py:87-91` contains a direct SQL query to find the latest version ID, bypassing the model layer (`app/models.py`). This violates the spec's Data Ownership table which says ALL database access goes through `app/models.py`.

## Findings

- **Source agent:** architecture-strategist
- **File:** `prompt-dashboard/app/blueprints/testing/routes.py:87-91`
- **The only instance** of raw SQL in any route file

## Proposed Solutions

### Solution A: Add model function (Recommended)

Add `get_latest_version_id(conn, prompt_id) -> int | None` to `models.py`:

```python
def get_latest_version_id(conn, prompt_id):
    row = conn.execute(
        'SELECT id FROM prompt_versions WHERE prompt_id = ? ORDER BY version_number DESC LIMIT 1',
        (prompt_id,)
    ).fetchone()
    return row['id'] if row else None
```

- **Effort:** Small (5 lines new, 5 lines replaced)
- **Risk:** None

## Acceptance Criteria

- [ ] No raw SQL in any route file
- [ ] New model function used in testing/routes.py

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-06-01 | Created from review | Only violation of data layer boundary |
