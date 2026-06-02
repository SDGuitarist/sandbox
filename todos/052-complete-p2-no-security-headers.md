---
status: pending
priority: p2
issue_id: "052"
tags: [code-review, security, run-061]
dependencies: []
---

# No Security Headers Configured

## Problem Statement

The application sets zero security headers. No `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`. Without CSP, any XSS that bypasses Jinja2 escaping (e.g., the `|safe` diff output) would have unrestricted script execution.

## Findings

- **Source agent:** security-sentinel
- **File:** `prompt-dashboard/app/__init__.py` (no `@app.after_request` handler)

## Proposed Solutions

### Solution A: Add after_request handler (Recommended)

```python
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    return response
```

- **Effort:** Small (5 lines)
- **Risk:** None

## Acceptance Criteria

- [ ] X-Content-Type-Options and X-Frame-Options headers present on all responses

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-06-01 | Created from review | Defense-in-depth for |safe usage |
