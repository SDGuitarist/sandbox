---
status: pending
priority: p2
issue_id: "053"
tags: [code-review, security, prompts-routes, run-061]
dependencies: []
---

# Unbounded system_prompt and user_prompt Size

## Problem Statement

`prompts/routes.py:63-64` (create) and `:129-130` (update) have no length validation for `system_prompt` and `user_prompt`. A multi-megabyte prompt would be stored in both `prompts` and `prompt_versions` tables, indexed by FTS5, and potentially sent to the Claude API (which would timeout after 60s).

## Findings

- **Source agent:** security-sentinel
- **File:** `prompt-dashboard/app/blueprints/prompts/routes.py:63-64,129-130`
- **Note:** `name` is capped at 200 chars and `description` at 1000, but prompts are unbounded

## Proposed Solutions

### Solution A: Add server-side length limits (Recommended)

Cap at 100,000 characters (generous for any prompt):

```python
system_prompt = request.form.get('system_prompt', '').strip()[:100000]
user_prompt = request.form.get('user_prompt', '').strip()[:100000]
```

- **Effort:** Small (2 lines per route, 2 maxlength attrs on templates)
- **Risk:** None

## Acceptance Criteria

- [ ] system_prompt and user_prompt truncated at 100,000 chars server-side
- [ ] Template textareas have maxlength attributes

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-06-01 | Created from review | DoS prevention |
