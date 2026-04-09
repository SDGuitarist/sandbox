---
status: pending
priority: p2
issue_id: "018"
tags: [code-review, architecture, finance-tracker]
dependencies: []
unblocks: []
sub_priority: 3
---

# 018 - Lazy import of `re` inside validate_year_month

## Problem Statement

`utils.py` does `import re` inside the `validate_year_month` function body instead of at module top. Per-call import overhead and non-standard Python convention.

## Findings

- **File:** `finance-tracker/app/utils.py`, line 32
- **Agent:** architecture-strategist

## Proposed Solutions

Move `import re` to the top of the file.

- Effort: Small
- Risk: None

## Work Log

- 2026-04-09: Created from code review
