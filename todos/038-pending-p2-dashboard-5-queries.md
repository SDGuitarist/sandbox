---
status: pending
priority: p2
issue_id: "038"
tags: [code-review, performance, brewops]
---

# Dashboard Fires 5 Batch Queries Where 1 Would Suffice

## Problem Statement
Dashboard route calls `get_batches_by_status()` 5 times (brewing, fermenting, conditioning, ready, tapped) -- 5 separate SQL queries. A single `WHERE status IN (...)` query would return all results in one round trip, reducing the dashboard from 8 queries to 4.

## Findings
- Performance reviewer: CRITICAL-1

## Proposed Solution
Add `get_batches_by_statuses(conn, statuses)` to batch_models.py, partition results in Python.

## Affected Files
- `app/models/batch_models.py` (new function)
- `app/routes/dashboard_routes.py` lines 18-27

## Acceptance Criteria
- [ ] Dashboard loads batch data in 1 query instead of 5
