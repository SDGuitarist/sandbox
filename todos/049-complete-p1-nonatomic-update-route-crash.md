---
status: pending
priority: p1
issue_id: "049"
tags: [code-review, data-integrity, prompts-routes, models, run-061]
dependencies: []
---

# Non-Atomic Update Route + TypeError Crash on Deleted Prompt

## Problem Statement

The `update()` route in `prompts/routes.py:110-144` checks if a prompt exists in one `with get_db()` block (lines 113-116), then performs the update in a separate `with get_db()` block (lines 140-141). If the prompt is deleted between check and update, `update_prompt()` in `models.py:200-203` crashes with `TypeError: 'NoneType' object is not subscriptable` when accessing `row['version_count']`.

Although both `with` blocks share the same `g.db` connection, no transaction protects the check-then-act sequence. The crash produces an unhandled 500 instead of a clean 404.

## Findings

- **Source agents:** kieran-python-reviewer, flow-trace-reviewer
- **Files:** `prompt-dashboard/app/blueprints/prompts/routes.py:110-144`, `prompt-dashboard/app/models.py:200-203`
- **Race window:** Between the first `with get_db()` exit (line 116) and the `BEGIN IMMEDIATE` inside `update_prompt()` (line 194)

## Proposed Solutions

### Solution A: Merge into single `with` block + guard in model (Recommended)

1. Move the existence check and update into the same `with get_db()` block in the route.
2. Add a guard in `update_prompt()` after fetching `version_count`:

```python
row = conn.execute('SELECT version_count FROM prompts WHERE id = ?', (prompt_id,)).fetchone()
if row is None:
    conn.execute('ROLLBACK')
    return None  # or raise LookupError
```

- **Effort:** Small (10 lines changed)
- **Risk:** None

## Acceptance Criteria

- [ ] Update route uses a single `with get_db()` block
- [ ] `update_prompt()` handles missing prompt gracefully (no TypeError)
- [ ] Route returns 404 if prompt doesn't exist

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-06-01 | Created from review | TOCTOU race in check-then-act pattern |
