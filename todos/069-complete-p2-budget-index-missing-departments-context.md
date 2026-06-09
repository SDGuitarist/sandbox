---
status: complete
priority: p2
issue_id: "069"
tags: [code-review, quality, budget, run-070]
dependencies: []
---

# 069 — Budget index route missing departments list in render context

## Problem Statement

`GET /budget/<project_id>` rendered `budget/index.html` without passing `departments` to the
template. The allocate form in the template needs a `<select name="department_id">` dropdown
populated from the departments list. Without it the form cannot render valid department choices.

## Fix Applied

Added `departments = get_departments(conn, project_id)` and passed it to the render_template
call in `app/blueprints/budget/routes.py` index route.

## Acceptance Criteria

- [x] `GET /budget/<pid>` template context includes `departments` list
- [x] Allocate form can render department dropdown
- [x] Smoke tests continue to pass

## Work Log

- 2026-06-08: Found during Run 070 review (P2-1). Fixed inline.
