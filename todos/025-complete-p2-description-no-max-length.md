---
status: pending
priority: p2
issue_id: "025"
tags: [code-review, input-validation, security, project-tracker]
dependencies: []
unblocks: []
sub_priority: 2
---

# Description Field Has No Max Length

## Problem Statement

`title` is capped at `[:100]` but `description` has no server-side length limit. A multi-megabyte POST could bloat the database and cause memory pressure.

## Findings

- `routes/tasks.py:36` (create) and `:91` (edit): `description = request.form.get('description', '').strip()` -- no truncation
- Template textarea at `templates/tasks/form.html:19` also lacks `maxlength`

**Agents:** kieran-python-reviewer (P3), security-sentinel (P2), architecture-strategist (P3)

## Proposed Solutions

### Option A: Add [:2000] truncation + HTML maxlength
- Effort: Small
- Risk: None

## Acceptance Criteria

- [ ] Server-side: `[:2000]` on description in both create and edit
- [ ] Template: `maxlength="2000"` on textarea
