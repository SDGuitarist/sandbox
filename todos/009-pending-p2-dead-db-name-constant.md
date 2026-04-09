---
status: resolved
priority: p2
issue_id: "009"
tags: [code-review, simplicity, dead-code]
dependencies: []
unblocks: []
sub_priority: 5
---

# Dead DB_NAME Constant in db.py

## Problem Statement

`DB_NAME = 'task_tracker_categories.db'` on line 5 of `db.py` is never
referenced. The actual database path comes from `app.config['DB_PATH']`.
Misleading -- a reader might think changing it would affect the database.

## Findings

- **Code Simplicity Reviewer (P2):** "Dead code, remove line 5."
- **Pattern Recognition (P1):** "Creates confusion about which value is
  actually used."

## Proposed Solutions

Delete line 5.

- Effort: Trivial
- Risk: None

## Acceptance Criteria

- [ ] DB_NAME constant removed from db.py
- [ ] No references to DB_NAME anywhere
