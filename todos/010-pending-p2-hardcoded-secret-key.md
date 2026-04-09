---
status: resolved
priority: p2
issue_id: "010"
tags: [code-review, security, flask]
dependencies: []
unblocks: []
sub_priority: 6
---

# Hardcoded SECRET_KEY

## Problem Statement

`app.config['SECRET_KEY'] = 'dev-task-tracker'` is hardcoded in __init__.py.
In sandbox this is low risk, but it sets a bad pattern for future swarm
builds to replicate.

## Findings

- **Security Sentinel (P2):** "Use os.environ.get('SECRET_KEY', 'dev-task-tracker')."
- **Pattern Recognition (P2):** "Add secret handling to spec template."
- **Architecture Strategist (P3):** "Swarm agents should have a rule about
  not hardcoding secrets."

## Proposed Solutions

```python
import os
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-task-tracker')
```

- Effort: Trivial
- Risk: None

## Acceptance Criteria

- [ ] SECRET_KEY reads from environment with dev fallback
