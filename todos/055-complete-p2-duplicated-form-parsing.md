---
status: pending
priority: p2
issue_id: "055"
tags: [code-review, code-quality, prompts-routes, run-061]
dependencies: []
---

# Duplicated Form Parsing in Create/Update Routes

## Problem Statement

`prompts/routes.py:52-73` (create) and `:118-138` (update) contain ~18 identical lines for parsing name, description, system_prompt, user_prompt, and tags from the form. This is a DRY violation and a maintenance risk — changes to validation must be applied in two places.

## Findings

- **Source agents:** kieran-python-reviewer, code-simplicity-reviewer
- **File:** `prompt-dashboard/app/blueprints/prompts/routes.py:52-73,118-138`

## Proposed Solutions

### Solution A: Extract helper function (Recommended)

```python
def _parse_prompt_form():
    name = request.form.get('name', '').strip()[:200]
    description = request.form.get('description', '').strip()[:1000]
    system_prompt = request.form.get('system_prompt', '').strip()
    user_prompt = request.form.get('user_prompt', '').strip()
    tags_raw = request.form.get('tags', '').strip()
    tag_names = [t.strip()[:50] for t in tags_raw.split(',') if t.strip()] if tags_raw else []
    return name, description, system_prompt, user_prompt, tag_names
```

- **Effort:** Small (10 lines new, ~18 lines removed)
- **Risk:** None

## Acceptance Criteria

- [ ] Single source of truth for form parsing
- [ ] Both create and update routes use the helper

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-06-01 | Created from review | Classic DRY extraction |
