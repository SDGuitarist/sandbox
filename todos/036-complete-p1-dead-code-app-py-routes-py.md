---
status: pending
priority: p1
issue_id: "036"
tags: [code-review, dead-code, architecture, brewops]
---

# Dead Code: app/app.py and app/routes.py From Different Project

## Problem Statement
Two files from a prior/different project remain in the codebase:
- `app/app.py` (14 lines) -- competing `create_app()` factory that imports nonexistent functions
- `app/routes.py` (148 lines) -- audit/event-sourcing API with endpoints for `/events` and `/entities`

Both reference functions (`append_event`, `get_events`, `get_projection`) that do not exist in the current `app/db.py`. Importing `app.app` would crash with ImportError. Having two `create_app()` in the same package is confusing.

## Findings
- Python reviewer: P1-1
- Architecture reviewer: H1
- Simplicity reviewer: 162 LOC of dead code

## Proposed Solution
Delete both files.

## Affected Files
- `app/app.py` (delete)
- `app/routes.py` (delete)

## Acceptance Criteria
- [ ] `app/app.py` removed
- [ ] `app/routes.py` removed
- [ ] `from app import create_app` still works (resolves to `app/__init__.py`)
