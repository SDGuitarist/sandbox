# Security Review -- GymFlow (Run 054)

**Date:** 2026-05-21
**Reviewer:** Security Sentinel (Claude Opus 4.6)
**Scope:** Full OWASP Top 10 + Feed-Forward risk (FC29 transaction boundary)
**Codebase:** Flask + SQLite + Jinja2 + Bootstrap 5 CDN, single-admin session auth

---

## Executive Summary

The GymFlow application demonstrates solid security fundamentals: all SQL queries
use parameterized statements, CSRF protection is globally enforced via Flask-WTF,
Jinja2 auto-escaping is active (no `|safe` filters), and session cookies are
correctly configured. However, several issues require attention, with the most
critical being the missing exception-path ROLLBACK in the attendance capacity
check (`check_in_class`) -- the exact Feed-Forward risk flagged by the plan.

**Overall Risk Rating:** MEDIUM. No critical exploitable vulnerabilities found,
but the transaction integrity gap and missing brute-force protection should be
addressed before production deployment.

---

## P1 (Must Fix)

### 1. Missing ROLLBACK on exception path in `check_in_class` (FC29 Feed-Forward Risk)

**File:** `gymflow/app/models/attendance.py`, lines 11-44

**Description:** The `check_in_class` function uses `conn.execute('BEGIN IMMEDIATE')`
for atomic capacity checking. The function handles the "class is full" case correctly
(line 30: explicit ROLLBACK before raising ValueError). However, if any exception
occurs between `BEGIN IMMEDIATE` (line 12) and `COMMIT` (line 42) -- for example,
a database constraint violation on the INSERT at line 34, or a `schedule_row`
being `None` at line 25 causing a `TypeError` -- the function raises without
executing ROLLBACK. This leaves the connection in an open transaction state.

**Impact:** An orphaned `BEGIN IMMEDIATE` transaction holds a write-lock on the
entire SQLite database. With WAL mode, this blocks all other writers until the
connection is closed by Flask's teardown handler. In pathological cases (rapid
requests to a nonexistent `class_schedule_id` that passes the route int validation
but has no row in the DB), the database could remain write-locked for the duration
of the request.

**Proof of concept:** POST to `/attendance/check-in` with a valid `member_id` and
a `class_schedule_id` that does not exist in `class_schedules`. Line 25
`schedule_row` is `None`, line 26 `capacity = schedule_row[0]` raises `TypeError`.
The BEGIN IMMEDIATE transaction is never rolled back.

**Remediation:** Wrap the entire transaction body in try/except with ROLLBACK in
the except clause, matching the pattern already used in `copy_week_schedules`
(schedule.py lines 159-176):

```python
def check_in_class(conn, member_id, class_schedule_id):
    conn.execute('BEGIN IMMEDIATE')
    try:
        row = conn.execute(
            'SELECT COUNT(*) FROM attendance WHERE class_schedule_id = ?',
            (class_schedule_id,)
        ).fetchone()
        count = row[0]

        schedule_row = conn.execute(
            'SELECT capacity FROM class_schedules WHERE id = ?',
            (class_schedule_id,)
        ).fetchone()
        if schedule_row is None:
            raise ValueError('Class schedule not found')
        capacity = schedule_row[0]

        if count >= capacity:
            raise ValueError('Class is full')

        cursor = conn.execute(
            'INSERT INTO attendance (member_id, class_schedule_id, attendance_type) '
            'VALUES (?, ?, ?)',
            (member_id, class_schedule_id, 'class')
        )
        attendance_id = cursor.lastrowid
        conn.execute('COMMIT')
        return attendance_id
    except Exception:
        conn.execute('ROLLBACK')
        raise
```

**TOCTOU verdict:** The capacity check itself is NOT vulnerable to TOCTOU. The
`BEGIN IMMEDIATE` acquires a write-lock before the count query, so no concurrent
writer can insert between the count and the insert. This is the correct SQLite
pattern. The only problem is the missing ROLLBACK on exception paths.

### 2. No duplicate check-in guard

**Files:** `gymflow/app/models/attendance.py` (check_in_class), `gymflow/schema.sql`

**Description:** There is no UNIQUE constraint on
`(member_id, class_schedule_id)` in the `attendance` table, and `check_in_class`
does not check whether the member is already checked in. A user could submit
the check-in form multiple times (e.g., double-click, back-button resubmission)
and create duplicate attendance records for the same member in the same class.
Each duplicate also decrements available capacity.

**Impact:** Data integrity issue. A member could consume all capacity slots by
repeated check-ins, preventing others from registering.

**Remediation:** Add a UNIQUE constraint or a pre-INSERT check:

```sql
-- Option A: Schema constraint (preferred)
CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_member_schedule
    ON attendance(member_id, class_schedule_id)
    WHERE class_schedule_id IS NOT NULL;
```

Or add a check inside the BEGIN IMMEDIATE block before the INSERT:

```python
existing = conn.execute(
    'SELECT id FROM attendance WHERE member_id = ? AND class_schedule_id = ?',
    (member_id, class_schedule_id)
).fetchone()
if existing:
    raise ValueError('Member already checked in to this class')
```

### 3. No login brute-force protection

**File:** `gymflow/app/blueprints/auth/routes.py`, lines 14-27

**Description:** The login endpoint accepts unlimited password attempts with no
rate limiting, account lockout, or delay. An attacker can run an automated
password-guessing attack against the single admin account.

**Impact:** With the default password `dev-password-123` being a weak dictionary
word pattern, and the production guard only checking equality against that exact
string, a brute-force attack could compromise admin access. The `hmac.compare_digest`
timing-safe comparison (good practice) does not help against volume-based attacks.

**Remediation:** Add rate limiting using Flask-Limiter or a simple in-memory
counter:

```python
# Simple approach: track failed attempts per IP
from collections import defaultdict
import time

_failed_attempts = defaultdict(list)
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300

def _is_rate_limited(ip):
    now = time.time()
    attempts = _failed_attempts[ip]
    # Prune old attempts
    _failed_attempts[ip] = [t for t in attempts if now - t < WINDOW_SECONDS]
    return len(_failed_attempts[ip]) >= MAX_ATTEMPTS
```

---

## P2 (Should Fix)

### 4. Default SECRET_KEY in development mode is predictable

**File:** `gymflow/app/__init__.py`, line 10

**Description:** `app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key')`.
While there IS a production guard (lines 11-12 raise RuntimeError if debug is off
and the key is the fallback), the development fallback key `dev-fallback-key` is
a well-known string. If someone accidentally deploys with `FLASK_DEBUG=1` (or
`app.debug=True`), the session cookies become forgeable.

**Impact:** Session forgery in misconfigured deployments.

**Remediation:** The existing production guard is good. Consider also logging a
warning when the fallback key is used, even in debug mode:

```python
if app.config['SECRET_KEY'] == 'dev-fallback-key':
    app.logger.warning('Using default SECRET_KEY -- do not use in production')
```

### 5. Default ADMIN_PASSWORD is a weak dictionary pattern

**File:** `gymflow/app/auth.py`, line 6

**Description:** `ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'dev-password-123')`.
The production guard in `__init__.py` (lines 28-29) correctly prevents this default
from being used in production. However, the default password follows a common
pattern and is checked via direct string comparison rather than a hashed value.

**Impact:** Low for production (guard exists), but the password is stored in
plaintext in both the environment variable and process memory. If the environment
is compromised or the process memory is dumped, the admin password is exposed.

**Remediation:** For a single-admin system, the env-var approach is acceptable
if deployment is properly secured. Consider hashing with `werkzeug.security`:

```python
# Store hash in env: ADMIN_PASSWORD_HASH=pbkdf2:sha256:...
from werkzeug.security import check_password_hash
ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH', '')

def check_password(password):
    return check_password_hash(ADMIN_PASSWORD_HASH, password)
```

### 6. No security headers configured

**File:** `gymflow/app/__init__.py`

**Description:** The application does not set any security response headers:
- No `Content-Security-Policy` header
- No `X-Content-Type-Options: nosniff`
- No `X-Frame-Options: DENY`
- No `Strict-Transport-Security` (HSTS)
- No `Referrer-Policy`

**Impact:** Without CSP, if an XSS vector is found (none currently exist thanks to
Jinja2 auto-escaping), there is no defense-in-depth layer. Without X-Frame-Options,
the app is vulnerable to clickjacking attacks. Without nosniff, browsers may
MIME-sniff responses.

**Remediation:** Add an `after_request` handler in the app factory:

```python
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "style-src 'self' https://cdn.jsdelivr.net; "
        "script-src 'self' https://cdn.jsdelivr.net"
    )
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response
```

### 7. No session expiration / timeout

**Files:** `gymflow/app/__init__.py`, `gymflow/app/auth.py`

**Description:** Sessions have no expiration. `session.permanent` is never set,
`PERMANENT_SESSION_LIFETIME` is never configured. Once logged in, the session
cookie persists until the browser is closed (default Flask behavior for
non-permanent sessions) or until manual logout.

**Impact:** If a user leaves a browser open on a shared computer, the session
remains active indefinitely.

**Remediation:**

```python
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# In the login route, after setting session['logged_in']:
session.permanent = True
```

### 8. `check_in_class` does not validate that `class_schedule_id` exists before proceeding

**File:** `gymflow/app/models/attendance.py`, line 24-26

**Description:** If `class_schedule_id` does not exist in `class_schedules`, the
query at line 24 returns `schedule_row = None`, and line 26 `schedule_row[0]`
raises `TypeError`. This is caught by the P1 fix above (ROLLBACK on exception),
but the error message would be a raw TypeError rather than a meaningful message.

This is related to P1 item 1 but deserves its own mention because the route
(`attendance/routes.py` line 79) catches only `ValueError`, not `TypeError`.
The TypeError propagates up as a 500 Internal Server Error.

**Impact:** 500 error exposed to user on invalid input. No data corruption
(FK constraint on `class_schedule_id` prevents orphan records), but poor error
handling and potential information leakage in debug mode.

**Remediation:** Add a None check in `check_in_class` (shown in P1 fix above) and
raise ValueError with a descriptive message. In the route, catch both ValueError
and TypeError, or widen to a general Exception with a generic flash message.

---

## P3 (Nice to Have)

### 9. No pagination on list endpoints

**Files:** All `list_*` routes across all blueprints

**Description:** Every list route fetches all records without pagination.
`get_all_members`, `get_all_invoices`, `get_all_payments`, etc. all execute
unbounded SELECT queries.

**Impact:** Denial-of-service vector. An attacker with admin access could create
thousands of records, causing list pages to consume excessive memory and
response time. Low likelihood in a single-admin system, but relevant if the
app scales.

### 10. No HTTPS enforcement at the application level

**File:** `gymflow/app/__init__.py`

**Description:** While `SESSION_COOKIE_SECURE` is set to `True` in non-debug mode
(line 13), there is no redirect from HTTP to HTTPS. The `Strict-Transport-Security`
header is also absent (covered in P2 item 6).

**Impact:** If deployed behind a reverse proxy that does not enforce HTTPS
redirects, users could access the app over HTTP, exposing session cookies and
form data.

### 11. Flash messages could reveal internal state on validation errors

**Files:** Various route files

**Description:** Most flash messages are generic ("Invalid password", "Member is
required"), which is good. But some exception handlers use `str(e)` to pass error
messages to users (e.g., attendance/routes.py line 82: `flash(str(e), 'error')`).
If the ValueError message changes or an unexpected exception type is caught,
internal details could leak.

**Impact:** Low. Currently all ValueError messages are developer-controlled
("Class is full"), but the pattern is fragile.

### 12. Bootstrap CDN loaded without Subresource Integrity on CSS

**File:** `gymflow/app/templates/base.html`, line 7-9

**Description:** The Bootstrap CSS link includes an `integrity` attribute with
a SHA-384 hash, and the JS bundle also has integrity checking. This is actually
correct -- both CDN resources have SRI attributes. No action needed.

**Status:** PASS -- no finding.

### 13. `isolation_level=None` in db.py disables Python's auto-transaction

**File:** `gymflow/app/db.py`, line 16

**Description:** Setting `isolation_level=None` puts the connection in
"autocommit" mode, which means every statement is its own transaction unless
explicitly wrapped in BEGIN/COMMIT. This is intentional (to allow the model
layer to manage its own transactions with `BEGIN IMMEDIATE`), but it means
that write operations without explicit `conn.commit()` or `BEGIN IMMEDIATE`
are auto-committed one statement at a time.

All model write functions do call `conn.commit()` or use `BEGIN IMMEDIATE`, so
this is correctly implemented. No action needed, but documenting this design
decision would be helpful.

**Status:** PASS -- correct by design.

---

## OWASP Top 10 Compliance Matrix

| # | Category | Status | Notes |
|---|----------|--------|-------|
| A01 | Broken Access Control | PASS | `login_required` on all non-auth routes. Single-admin model has no privilege escalation surface. |
| A02 | Cryptographic Failures | WARN | Admin password stored in plaintext env var (P2-5). Session key has production guard. |
| A03 | Injection (SQLi) | PASS | All queries use parameterized `?` placeholders. `search_members` correctly parameterizes LIKE with `%{query}%` via bind variable (not string concat). |
| A04 | Insecure Design | WARN | No duplicate check-in guard (P1-2). No brute-force protection (P1-3). |
| A05 | Security Misconfiguration | WARN | No security headers (P2-6). Default secrets have production guards (good). |
| A06 | Vulnerable Components | INFO | Bootstrap 5.3.3 loaded via CDN with SRI. No pip dependencies beyond Flask/Flask-WTF visible. |
| A07 | Auth Failures | WARN | No rate limiting on login (P1-3). No session timeout (P2-7). |
| A08 | Data Integrity Failures | WARN | Missing ROLLBACK on exception path (P1-1). |
| A09 | Logging & Monitoring | INFO | No audit logging of admin actions (login, data changes, deletes). |
| A10 | SSRF | N/A | No outbound HTTP requests from the application. |

---

## Security Checklist

- [x] All inputs validated and sanitized (comprehensive validation in all routes)
- [x] No hardcoded secrets in source code (env vars with production guards)
- [x] Proper authentication on all endpoints (`login_required` decorator)
- [x] SQL queries use parameterization (all queries use `?` placeholders)
- [x] XSS protection implemented (Jinja2 auto-escaping, no `|safe` filters)
- [ ] HTTPS enforced where needed (no app-level enforcement)
- [x] CSRF protection enabled (Flask-WTF CSRFProtect, tokens in all forms)
- [ ] Security headers properly configured (none set)
- [x] Error messages don't leak sensitive information (generic messages used)
- [ ] Session management hardened (no expiration, no brute-force protection)

---

## Feed-Forward Verdict (FC29)

The Feed-Forward risk about "Attendance capacity check with BEGIN IMMEDIATE --
transaction boundary between attendance_models and attendance_routes agents"
is **partially validated**:

1. **TOCTOU race:** NOT present. The `BEGIN IMMEDIATE` correctly serializes
   the read-check-write sequence. The capacity check is atomic.
2. **ROLLBACK on error paths:** INCOMPLETE. The "class is full" path has an
   explicit ROLLBACK, but all other exception paths (TypeError from None
   schedule_row, IntegrityError from duplicate FK, etc.) leave the transaction
   orphaned. **This is P1-1 above.**
3. **Double-commit:** NOT present. The function uses `conn.execute('COMMIT')`
   exactly once on the success path.
4. **Orphaned transaction state:** PRESENT on exception paths (P1-1).

The `copy_week_schedules` function in `schedule.py` uses the correct
try/except/ROLLBACK pattern. The `check_in_class` function should match it.

---

## Remediation Roadmap

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P1 | Fix ROLLBACK on exception paths in check_in_class | 15 min | Prevents write-lock starvation |
| P1 | Add duplicate check-in guard | 15 min | Prevents data integrity corruption |
| P1 | Add login rate limiting | 30 min | Prevents brute-force password attacks |
| P2 | Add security response headers | 15 min | Defense-in-depth against XSS, clickjacking |
| P2 | Add session expiration | 10 min | Limits session hijacking window |
| P2 | Validate class_schedule_id existence in check_in_class | 5 min | Prevents 500 errors on bad input |
| P2 | Hash admin password | 20 min | Protects against env/memory dump |
| P3 | Add pagination to list endpoints | 2 hrs | Prevents memory exhaustion |
| P3 | Add audit logging | 1 hr | Enables incident investigation |
