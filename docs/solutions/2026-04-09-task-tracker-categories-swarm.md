---
title: "Task Tracker with Project Categories (Swarm Build)"
date: 2026-04-09
tags: [flask, sqlite, swarm, parallel-agents, integration-test]
app: task-tracker-categories
agents: 4
merge_conflicts: 0
post_assembly_fixes: 1
mismatch_count: 1
---

# Task Tracker with Project Categories -- Swarm Build

## What Was Built

A Flask web app with project categories (color-coded), task CRUD, completion
toggle, and a dashboard with progress bars. Built by 4 parallel agents in
isolated worktrees, assembled via sequential merge.

## What Went Wrong

### Bug: create_project return type mismatch

Agent 2 (Projects) wrote `project = create_project(conn, name, color)` and
then accessed `project.id`. But `create_project()` returns an `int` (the new
row ID), not a `sqlite3.Row`. The route should have been
`project_id = create_project(...)`.

**Root cause:** The spec said `create_project` returns `int (new id)`, but
Agent 2 named the variable `project` and treated it as a Row. The spec was
correct; the agent misread it.

**Fix:** One-line change in routes.py. Caught by the smoke test during
assembly verification.

**Lesson:** The spec should include a usage example for every model function
that returns a scalar (not a Row). The acid test spec had this for
`get_dashboard_stats` but not for `create_*` functions. Add:
```python
# Usage: create_project returns an int, not a Row
project_id = create_project(conn, name, color)
redirect(url_for('...', project_id=project_id))
```

## What Went Right

1. **Zero merge conflicts** -- 4 agents, 19 files, zero overlaps. The
   ownership gate confirmed each agent only touched its assigned files.
2. **Template inheritance worked** -- All 5 page templates extend layout.html
   correctly. The prescriptive layout block in the spec prevented mismatches.
3. **get_db() context manager used correctly** -- All agents used
   `with get_db() as conn:` (not `conn = get_db()`). The anti-pattern example
   in the spec was effective.
4. **WAL mode + foreign keys enabled** -- No `database is locked` errors
   during testing.
5. **CASCADE delete worked** -- Deleting a project removed its tasks.
6. **Color handling via inline styles** -- No CSS class generation needed.

## Swarm Path Results

| Step | Status | Notes |
|------|--------|-------|
| Ownership gate | PASS | 0 violations across 4 agents |
| Assembly merge | PASS | 0 conflicts across 4 sequential merges |
| Spec contract check | PASS | Blueprint names, template inheritance, render context all match |
| Smoke test | 1 FAIL, then PASS | create_project return type bug fixed |
| All 6 acceptance checkpoints | PASS | After fix |

## Comparison: Solo vs Swarm

| Metric | Solo (habit tracker) | Swarm (task tracker) |
|--------|---------------------|---------------------|
| Files | 1 | 19 |
| Agents | 1 | 4 |
| Total agent time | ~60s | ~58s (parallel) |
| Merge conflicts | N/A | 0 |
| Post-build fixes | 1 (date dedup) | 1 (return type) |
| Spec lines | N/A | ~400 |

## Key Patterns

1. **Prescriptive code blocks prevent mismatches** -- Exact code for
   `__init__.py`, layout.html, and blueprint registration had 0 errors.
2. **Usage examples for return types** -- Functions returning scalars need
   example variable naming in the spec to prevent `.id` on an `int`.
3. **Anti-pattern examples work** -- The `conn = get_db()` anti-pattern
   example prevented all 3 blueprint agents from making this mistake.
4. **Inline styles for dynamic values** -- Using `style="background-color: ..."` 
   avoided the need for dynamic CSS class generation.

## Risk Resolution

**Brainstorm risk:** "Whether the template agent can produce working HTML
without seeing the actual route return values."

**What happened:** Template Render Context (Section 8) in the spec fully
resolved this. All template variable references matched. The spec was ~400
lines, with ~80 lines dedicated to render context. The investment paid off.

**Lesson:** For Flask swarm builds, the Template Render Context section is
non-negotiable. Budget ~20% of spec lines for it.
