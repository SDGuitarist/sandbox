---
status: pending
priority: p3
issue_id: "021"
tags: [code-review, quality, finance-tracker]
dependencies: []
unblocks: []
sub_priority: 2
---

# 021 - Repeated fetch-categories-and-render blocks in transactions routes

## Problem Statement

The transaction create and edit routes repeat the pattern of fetching categories and re-rendering the form 5 times (~40 duplicated lines).

## Findings

- **File:** `finance-tracker/app/blueprints/transactions/routes.py`
- **Agent:** simplicity-reviewer

## Proposed Solutions

Extract a helper function `_render_transaction_form(transaction, is_edit, conn=None)`.

- Effort: Small
- Risk: Low

## Work Log

- 2026-04-09: Created from code review
