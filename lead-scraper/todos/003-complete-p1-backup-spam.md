---
status: resolved
priority: p1
issue_id: "003"
tags: [code-review, quality]
---

# migrate_db creates backup on every init_db call

## Problem Statement
Every CLI invocation and Flask startup creates a new backup file, even when no migration is needed. Already 10+ backup files from one evening.

## Proposed Solution
Only create backup when columns actually need adding. Check first, backup only if `to_add` is non-empty.

## Acceptance Criteria
- [ ] No backup created when schema is already up to date
- [ ] Backup still created when columns need adding
