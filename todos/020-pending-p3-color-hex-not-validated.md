---
status: pending
priority: p3
issue_id: "020"
tags: [code-review, security, finance-tracker]
dependencies: []
unblocks: []
sub_priority: 1
---

# 020 - Color field not validated as hex format

## Problem Statement

Category color input is stored without validating it's a valid hex color (#xxxxxx). Arbitrary strings in the color field end up in `style` attributes via templates.

## Findings

- **File:** `finance-tracker/app/blueprints/categories/routes.py`
- **Agent:** security-sentinel

## Proposed Solutions

Add regex validation: `if not re.match(r'^#[0-9a-fA-F]{6}$', color): flash error`

- Effort: Small
- Risk: None (Jinja2 auto-escapes, but defense in depth)

## Work Log

- 2026-04-09: Created from code review
