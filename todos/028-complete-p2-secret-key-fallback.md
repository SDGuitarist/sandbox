---
status: pending
priority: p2
issue_id: "028"
tags: [code-review, security, project-tracker]
dependencies: []
unblocks: []
sub_priority: 5
---

# SECRET_KEY Hardcoded Fallback

## Problem Statement

`app.py:22` falls back to `'dev-key-change-in-prod'` if SECRET_KEY env var not set. Known key = CSRF tokens forgeable + session cookies tamperable. For sandbox: acceptable but should be documented as intentional.

## Findings

- `app.py:22`: `app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-prod')`
- This is a pattern that gets copied to future builds

**Agent:** security-sentinel (P1 -- downgraded to P2 for sandbox context)

## Proposed Solutions

### Option A: Document as intentional in code comment
```python
# WARNING: dev-only fallback. Set SECRET_KEY in production.
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-prod')
```
- Effort: Small
- Risk: None

## Acceptance Criteria

- [ ] Comment added explaining this is dev-only
