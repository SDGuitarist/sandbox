---
status: pending
priority: p2
issue_id: "019"
tags: [code-review, quality, finance-tracker]
dependencies: []
unblocks: []
sub_priority: 4
---

# 019 - Duplicated WHERE clause in get_transactions and get_transaction_count

## Problem Statement

`get_transactions` and `get_transaction_count` build identical WHERE clauses independently (~20 duplicated lines). Extract a shared helper.

## Findings

- **File:** `finance-tracker/app/models.py`, lines 30-51 and 54-67
- **Agents:** simplicity-reviewer, performance-oracle

## Proposed Solutions

Extract `_build_transaction_where(year_month, category_id)` returning `(where_clause, params)`.

- Effort: Small
- Risk: Low

## Work Log

- 2026-04-09: Created from code review
