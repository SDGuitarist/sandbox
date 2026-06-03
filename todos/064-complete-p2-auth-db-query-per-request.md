---
status: complete
priority: p2
issue_id: "064"
tags: [code-review, performance, auth, database, run-064]
dependencies: []
---

# P2: auth_helpers.py Makes DB Query on Every Authenticated Request

## Problem Statement

`login_required` and `admin_required` both query `SELECT * FROM users WHERE id = ?` on every authenticated request. The session already contains `user_id`, `username`, and `role`. For `admin_required`, the role check could be done from the session before the DB query, avoiding unnecessary round-trips.

## Findings

- **File:** `app/auth_helpers.py` lines 6-19 (`login_required`), lines 22-37 (`admin_required`)
- **Pattern:** Both decorators: check session → DB query → set g.user
- **Impact:** Every authenticated page load = 1 extra SELECT. Fine for SQLite at small scale, bad pattern as load grows.

## Proposed Solution

**Option A (Recommended):** Short-circuit admin check before DB query

```python
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        # Short-circuit: check role from session before DB query
        if session.get('role') != 'admin':
            abort(403)
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = ?',
                            (session['user_id'],)).fetchone()
        if user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        g.user = user
        return f(*args, **kwargs)
    return decorated
```

**Effort:** Small
**Risk:** Low — semantically equivalent, adds session-layer fast-path

## Acceptance Criteria

- [ ] `admin_required` checks `session['role']` before DB query
- [ ] Non-admin user blocked from /admin returns 403 (no regression)
- [ ] Smoke test "Non-admin blocked from /admin" still PASSES

## Work Log

- 2026-06-02: Found during Run 064 tail review.
