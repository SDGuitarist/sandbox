---
status: pending
priority: p2
issue_id: "057"
tags: [code-review, security, auth, devex, run-063]
dependencies: []
---

# 057 — SESSION_COOKIE_SECURE=True unconditional, breaks local HTTP dev

## Problem Statement

`app/__init__.py` sets `SESSION_COOKIE_SECURE = True` unconditionally.
When the app runs over plain HTTP (local dev, `flask run`), browsers refuse to
send session cookies to non-HTTPS origins, so users cannot log in. The smoke
test passes because it uses Flask's test client (no real HTTP), masking this.

## Findings

- **File:** `app/__init__.py` line 18
- **Impact:** Any developer running `flask run` locally without HTTPS gets an
  app that appears to work (200s) but session auth silently fails — every
  authenticated route redirects to login despite successful form submission.
- **Contrast:** WTF_CSRF_ENABLED and TESTING are never set, so CSRF is always
  enabled (correct). Only SESSION_COOKIE_SECURE needs to be conditional.
- **Pattern:** Flask docs recommend `SESSION_COOKIE_SECURE = not app.debug`
  or reading from an env var.

## Proposed Solutions

### Option A: Conditional on FLASK_ENV / env var (Recommended)
```python
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
```
Effort: Trivial. Risk: None.

### Option B: Conditional on app.debug
```python
app.config['SESSION_COOKIE_SECURE'] = not app.debug
```
Effort: Trivial. Risk: None. Standard Flask pattern.

### Option C: Explicit env var
```python
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
```
Effort: Trivial. Explicit. Requires docs update.

## Recommended Action

Option A — uses FLASK_ENV which is already the de-facto Flask deployment signal.

## Technical Details

- **Affected file:** `app/__init__.py` line 18
- **Note:** `.env.example` (if present) should document `FLASK_ENV=production`

## Acceptance Criteria

- [ ] Local dev (`flask run` over HTTP) allows session login
- [ ] Production (FLASK_ENV=production) still sets SESSION_COOKIE_SECURE=True
- [ ] Smoke test continues to pass (uses test client, unaffected)

## Work Log

- 2026-06-02: Found during Run 063 review — security/devex gap
