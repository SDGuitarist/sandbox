---
status: pending
priority: p2
issue_id: "054"
tags: [code-review, architecture, run-061]
dependencies: []
---

# test_smoke.py Listed in .gitignore

## Problem Statement

`prompt-dashboard/.gitignore` includes `test_smoke.py` on line 1. The spec explicitly assigns this file to the `core` agent as a mandatory verification artifact. Ignoring it means clones won't get the smoke tests.

## Findings

- **Source agent:** architecture-strategist
- **File:** `prompt-dashboard/.gitignore:1`

## Proposed Solutions

### Solution A: Remove from .gitignore (Recommended)

Remove the `test_smoke.py` line from `.gitignore`.

- **Effort:** Small (1 line)
- **Risk:** None

## Acceptance Criteria

- [ ] test_smoke.py is tracked by git

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-06-01 | Created from review | Swarm agent likely auto-added to gitignore |
