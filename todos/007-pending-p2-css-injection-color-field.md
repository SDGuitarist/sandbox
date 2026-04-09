---
status: resolved
priority: p2
issue_id: "007"
tags: [code-review, security, flask]
dependencies: []
unblocks: []
sub_priority: 3
---

# CSS Injection via Unvalidated Color Input

## Problem Statement

The `project.color` value is rendered directly in a `style` attribute in
`detail.html`. Jinja2 auto-escaping does not protect against CSS injection
inside style attributes.

## Findings

- **Security Sentinel (P2):** "A user could submit a color value like
  `red; background-image: url('https://evil.com/...')`. Limited in modern
  browsers but violates defense-in-depth."

## Proposed Solutions

Server-side regex validation:
```python
import re
COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
if not COLOR_RE.match(color):
    color = '#6366f1'
```

- Effort: Small (add to projects/routes.py)
- Risk: None

## Acceptance Criteria

- [ ] Color input validated as hex format on both create and update routes
