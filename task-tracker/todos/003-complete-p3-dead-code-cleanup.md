---
status: pending
priority: p3
issue_id: "003"
tags: [code-review, simplicity]
dependencies: []
---

# Dead Code Cleanup

## Problem Statement

Minor dead code artifacts from the 4-agent parallel build.

## Findings

- `db.py` line 7: `DB_NAME = 'task_tracker.db'` defined but never imported anywhere
- `style.css` line 213-215: `.description` class defined but templates use inline style
- Source: code-simplicity-reviewer

## Proposed Solutions

### Option A: Remove dead code
- Delete `DB_NAME` from db.py
- Delete `.description` from style.css
- Effort: Trivial | Risk: None
