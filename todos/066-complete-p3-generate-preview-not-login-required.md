---
status: complete
priority: p3
issue_id: "066"
tags: [code-review, auth, wizard, login-required, run-064]
dependencies: []
---

# P3: generate_preview Route Missing @login_required

## Problem Statement

The `generate_preview()` route (POST /wizard/generate) is missing `@login_required`. All other wizard routes have it. Anonymous users can submit form data to `/wizard/generate` and receive a generated prompt preview.

## Findings

- **File:** `app/blueprints/wizard/routes.py` line 155-187 (`generate_preview`)
- **Pattern:** FC27 (Neighbor Pattern Skip) — adjacent routes all have `@login_required`
- **Impact:** Minor — component definitions are not sensitive data. No PII or user data exposed. Consistency violation.

## Proposed Solution

Add `@login_required` decorator above `generate_preview`:

```python
@bp.route('/generate', methods=['POST'])
@login_required  # Add this
def generate_preview():
    ...
```

**Effort:** Trivial (1 line)
**Risk:** None

## Acceptance Criteria

- [ ] `generate_preview` has `@login_required` decorator
- [ ] Anonymous POST to /wizard/generate redirects to login (302)

## Work Log

- 2026-06-02: Found during Run 064 tail review.
