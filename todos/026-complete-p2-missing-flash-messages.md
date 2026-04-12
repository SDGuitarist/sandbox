---
status: pending
priority: p2
issue_id: "026"
tags: [code-review, consistency, project-tracker]
dependencies: []
unblocks: []
sub_priority: 3
---

# Missing Success Flash Messages on Tasks and Members Routes

## Problem Statement

Categories routes flash on create/edit/delete success, but tasks and members routes do not. This is a swarm consistency gap -- 3 agents made different decisions about user feedback.

## Findings

- `routes/categories.py:43,85,99` -- flashes on success
- `routes/tasks.py` -- no success flashes anywhere
- `routes/members.py` -- no success flashes anywhere

**Agents:** kieran-python-reviewer (P2), architecture-strategist (P2)

## Proposed Solutions

### Option A: Add flash messages to tasks and members (Recommended)
Add `flash('Task created', 'success')` etc. to match categories pattern.
- Effort: Small (6 additions across 2 files)
- Risk: None

## Acceptance Criteria

- [ ] Tasks: flash on create, edit, delete
- [ ] Members: flash on create, edit, delete
- [ ] Pattern matches categories routes
