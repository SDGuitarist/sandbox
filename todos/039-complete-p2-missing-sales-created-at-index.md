---
status: pending
priority: p2
issue_id: "039"
tags: [code-review, performance, schema, brewops]
---

# Missing Index on sales.created_at + Function Prevents Index Use

## Problem Statement
`get_today_sales_total` filters on `date(created_at) = date('now')` -- a full table scan because: (1) no index on created_at, and (2) the `date()` function wrapping prevents index use even if one existed. Sales is the highest-growth table (~100/day).

## Findings
- Performance reviewer: CRITICAL-3 (P0 in their priority)

## Proposed Solution
1. Add index: `CREATE INDEX idx_sales_created_at ON sales(created_at)`
2. Rewrite query to use range scan: `WHERE created_at >= date('now') AND created_at < date('now', '+1 day')`

## Affected Files
- `schema.sql` (add index)
- `app/models/sale_models.py` line 30 (rewrite query)

## Acceptance Criteria
- [ ] Today's sales total uses index range scan, not full table scan
