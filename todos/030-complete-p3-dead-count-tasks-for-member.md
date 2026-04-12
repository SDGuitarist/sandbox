---
status: pending
priority: p3
issue_id: "030"
tags: [code-review, dead-code, project-tracker]
dependencies: []
unblocks: []
sub_priority: 2
---

# Dead Function: count_tasks_for_member

## Problem Statement

`models/members.py:40-46` defines `count_tasks_for_member()` but no route or template calls it. Classic YAGNI. The members detail page already receives the full task list via `get_tasks_by_member` and can use `{{ tasks|length }}`.

## Findings

**Agent:** code-simplicity-reviewer

## Proposed Solutions

Delete `models/members.py:40-46`.

## Acceptance Criteria

- [ ] Function removed
- [ ] No references to it exist in routes or templates
