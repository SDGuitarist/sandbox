# Security Audit: Solopreneur Command Center

**Date:** 2026-05-19
**Auditor:** Security Sentinel (Claude Opus 4.6)
**Scope:** Full application -- 14 blueprints, ~12,800 lines, Flask + SQLite + Jinja2
**App root:** `/Users/alejandroguillen/Projects/sandbox/command-center/`

---

## Executive Summary

The application has a **solid security foundation**: all SQL queries use parameterized
statements, CSRF protection is globally enabled, Jinja2 autoescaping prevents most XSS,
and werkzeug's `generate_password_hash` handles passwords correctly. However, there are
several findings that range from critical architecture gaps to hardening improvements.

**Overall risk: MEDIUM.** The highest-severity issues are the multi-tenant isolation
gap (all data tables lack `user_id` scoping) and session fixation on login. For a
single-user local app these are theoretical, but they become critical if the app is
ever deployed multi-user or internet-facing.

### Finding Count by Severity

| Severity | Count |
|----------|-------|
| P1 (must fix) | 5 |
| P2 (should fix) | 7 |
| P3 (nice to have) | 5 |

---

## Detailed Findings

### P1-01: Session Fixation on Login

**File:** `app/auth/routes.py`, lines 34 and 78
**Issue:** After successful login or registration, the session ID is not regenerated.
The code does `session['user_id'] = user['id']` without first calling `session.clear()`
or `session.regenerate()`. If an attacker can set a session cookie before the user logs
in (via a fixation attack), they inherit the authenticated session.

**Impact:** Session hijacking. An attacker who can set a cookie on the victim's browser
gets full access to the victim's account.

**Remediation:**
```python
# In login(), before setting user_id:
session.clear()
session['user_id'] = user['id']

# In register(), before setting user_id:
session.clear()
session['user_id'] = user_id
```

The `session.clear()` in Flask regenerates the session ID because it replaces the
session dict entirely. The logout route already calls `session.clear()` -- the same
pattern needs to happen at login.

---

### P1-02: No Multi-Tenant Data Isolation (IDOR by Design)

**File:** `app/schema.sql` (entire schema); every `routes.py` file
**Issue:** Only the `business_profile` table has a `user_id` column. All other data
tables (`contact`, `company`, `deal`, `project`, `task`, `time_entry`, `income`,
`expense`, `note`, `journal_entry`, `goal`) have **no user_id column**. Every query
like `SELECT * FROM contact WHERE id = ?` returns any user's data regardless of who
is logged in.

If two users register, User A can view/edit/delete all of User B's contacts, deals,
projects, income, expenses, and time entries simply by guessing or enumerating integer
IDs.

**Impact:** Complete data exposure and manipulation across users. For a financial app
handling revenue, expenses, and invoicing, this is a critical business risk.

**Remediation:** Add a `user_id INTEGER NOT NULL` column to every data table, add a
foreign key to `user(id)`, and filter every query by `session['user_id']`. This is a
significant refactor but is essential before any multi-user deployment.

**Note:** If this app is strictly single-user-per-instance (one SQLite DB per user),
this is low-risk by design. Document that assumption explicitly.

---

### P1-03: Open Redirect via `request.form.get('next')` and `request.referrer`

**Files:**
- `app/tasks/routes.py`, line 330: `next_url = request.form.get('next', url_for('tasks.index'))`
- `app/tasks/routes.py`, lines 343, 364: `redirect(request.referrer or ...)`
- `app/contacts/routes.py`, lines 265, 283: `redirect(request.referrer or ...)`

**Issue:** The `next` parameter from form data is passed directly to `redirect()`
without validating that it is a relative URL on the same domain. An attacker can craft
a form that submits `next=https://evil.com/phish` and the user is redirected there
after completing the action. Similarly, `request.referrer` is user-controlled via the
`Referer` header and can be any URL.

**Impact:** Phishing attacks. After a user completes a legitimate action (task complete,
quick-add), they are silently redirected to an attacker-controlled page.

**Remediation:**
```python
from urllib.parse import urlparse

def safe_redirect(target, fallback):
    """Only redirect to same-origin paths."""
    if target:
        parsed = urlparse(target)
        # Only allow relative URLs (no scheme or netloc)
        if not parsed.scheme and not parsed.netloc:
            return redirect(target)
    return redirect(fallback)
```

---

### P1-04: Auth Templates Output Bare CSRF Token (Broken CSRF)

**Files:**
- `app/templates/auth/login.html`, line 24
- `app/templates/auth/register.html`, line 24
- `app/templates/auth/setup.html`, line 25

**Issue:** These templates output `{{ csrf_token() }}` as bare text inside the form
rather than wrapping it in `<input type="hidden" name="csrf_token" value="...">`. The
`csrf_token()` function in Flask-WTF returns just the token string. Without the hidden
input element, the token is rendered as visible text in the page and is **not submitted
with the form POST**. Flask-WTF's `CSRFProtect` validates the `csrf_token` field in
form data -- if it is missing, CSRF protection is bypassed on these three critical
endpoints.

**Impact:** Login CSRF (attacker logs victim into attacker's account to capture data),
registration CSRF, and setup CSRF.

**Remediation:** Change all three templates from:
```html
{{ csrf_token() }}
```
to:
```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

All other templates in the application already use the correct pattern.

---

### P1-05: Unprotected Registration Endpoint (No Rate Limiting)

**File:** `app/auth/routes.py`, `register()` function
**Issue:** The registration endpoint has no rate limiting, no CAPTCHA, and no
invitation-only gating. Anyone who discovers the URL can create unlimited accounts.
Combined with P1-02 (no data isolation), this means an attacker can register, then
access all existing users' data.

**Impact:** Mass account creation, data exfiltration, abuse.

**Remediation (simplest):** Add a registration-allowed flag or invitation code check.
For a solopreneur tool, the simplest fix is:
```python
@bp.route('/register', methods=['GET', 'POST'])
def register():
    # Prevent registration if any user already exists
    with get_db() as db:
        existing_users = db.execute("SELECT COUNT(*) as c FROM user").fetchone()['c']
    if existing_users > 0:
        flash('Registration is closed.', 'error')
        return redirect(url_for('auth.login'))
    # ... rest of registration
```

---

### P2-01: Missing `SESSION_COOKIE_SECURE` Flag

**File:** `app/__init__.py`, line 12-13
**Issue:** The app sets `SESSION_COOKIE_HTTPONLY = True` and `SESSION_COOKIE_SAMESITE = 'Lax'`
but does not set `SESSION_COOKIE_SECURE = True`. Without this flag, the session cookie
is sent over plain HTTP, making it interceptable via network sniffing.

**Impact:** Session hijacking on non-HTTPS connections.

**Remediation:**
```python
app.config['SESSION_COOKIE_SECURE'] = True  # Only send cookie over HTTPS
```

If the app also needs to work in local development (HTTP), use an environment variable:
```python
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') != 'development'
```

---

### P2-02: No Security Response Headers

**File:** `app/__init__.py`
**Issue:** The application does not set any security headers:
- No `X-Content-Type-Options: nosniff`
- No `X-Frame-Options: DENY`
- No `Content-Security-Policy`
- No `Strict-Transport-Security`
- No `Referrer-Policy`

**Impact:** Clickjacking attacks (iframe embedding), MIME-type confusion, missing
defense-in-depth layers.

**Remediation:** Add an `after_request` handler:
```python
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response
```

---

### P2-03: `_get_or_create_profile` Calls `conn.commit()` Inside `get_db()` Context

**File:** `app/settings/routes.py`, lines 36-52
**Issue:** The `_get_or_create_profile` function calls `conn.commit()` directly on the
connection while the caller may have opened it with `get_db(immediate=True)` which
manages its own commit/rollback cycle. This breaks the transaction boundary -- if a
later operation in the same `with` block fails, the profile INSERT has already been
committed and cannot be rolled back.

However, looking more closely, this function is called both inside `get_db(immediate=True)`
blocks (POST handlers) and `get_db()` blocks (GET handlers). When called inside a
non-immediate context, the `conn.commit()` is correct because there is no auto-commit.
When called inside an immediate context, it interferes with the transaction.

**Impact:** Potential data inconsistency -- a profile could be created but the
subsequent update could fail, leaving the profile in a default state.

**Remediation:** Remove the `conn.commit()` call from `_get_or_create_profile` and
ensure the function is always called within a `get_db(immediate=True)` context for
write operations.

---

### P2-04: Uncaught `ValueError` in Settings Financial/Targets Handlers

**File:** `app/settings/routes.py`, lines 105 and 113
**Issue:** The `financial()` and `targets()` POST handlers use bare `int(float(...))` and
`int(request.form.get(...))` conversions without try/except:

```python
rate_cents = int(float(rate_dollars) * 100)           # line 105
int(request.form.get('fiscal_year_start', 1)),        # line 113
int(request.form.get('weekly_hours_target', 40)),      # line 149
```

If a user submits a non-numeric string for these fields, a `ValueError` exception
propagates uncaught, resulting in a 500 error. In debug mode, this exposes the stack
trace (which reveals file paths and code structure).

**Impact:** Information disclosure in debug mode; poor user experience in production.

**Remediation:** Wrap all `int(float(...))` conversions in try/except blocks, consistent
with how `revenue/routes.py` and `pipeline/routes.py` handle the same pattern.

---

### P2-05: Race Condition in User Registration

**File:** `app/auth/routes.py`, lines 61-78
**Issue:** The uniqueness check and INSERT happen in two separate database connections:

```python
with get_db() as db:                          # Connection 1: read-only
    existing = db.execute("SELECT id FROM user WHERE email = ?", ...).fetchone()

if existing is not None:
    flash(...)
    return ...

with get_db(immediate=True) as db:            # Connection 2: write
    db.execute("INSERT INTO user ...")
```

Between the check and the insert, another request could register the same email. The
`email UNIQUE` constraint in SQL will catch this and raise an exception, but that
exception is not handled -- resulting in a 500 error.

**Impact:** Unhandled exception on concurrent registration of the same email. Not
exploitable for data corruption (the UNIQUE constraint protects integrity), but causes
a bad user experience and potential 500 error page information leakage.

**Remediation:** Either (a) combine the check and insert into a single
`get_db(immediate=True)` block, or (b) catch the `sqlite3.IntegrityError` and flash
a friendly message.

---

### P2-06: No Input Validation on Money Amounts (Negative Values Accepted)

**Files:**
- `app/pipeline/routes.py`, lines 128-132 (deal value)
- `app/projects/routes.py`, line 149 (project value, hourly_rate)
- `app/goals/routes.py`, lines 79-80 (revenue_target)
- `app/settings/routes.py`, lines 104-105 (hourly_rate)

**Issue:** The money parsing pattern `int(float(value_str) * 100)` accepts negative
numbers. A user (or attacker) can submit `-5000` as a deal value, project value, or
hourly rate. Unlike income and expenses (which check `amount <= 0`), these fields have
no server-side validation against negative values.

Additionally, there is no upper bound validation. Extremely large values (e.g.,
`999999999999999`) could cause integer overflow in calculations like weighted pipeline
value.

**Impact:** Corrupted business metrics, misleading dashboard data, potential calculation
errors in reports.

**Remediation:** Add validation after parsing:
```python
if value < 0:
    flash("Value cannot be negative.", "error")
    return ...
```

---

### P2-07: Debug Mode Enabled in `run.py`

**File:** `command-center/run.py`, line 6
```python
app.run(debug=True, port=5000)
```

**Issue:** Debug mode is hardcoded to `True`. This enables the Werkzeug debugger, which
provides an interactive Python console in the browser when an exception occurs. If the
app is accidentally exposed to the network, anyone who triggers an error gets a remote
code execution shell.

**Impact:** Remote code execution if the app is network-accessible.

**Remediation:**
```python
import os
app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true', port=5000)
```

---

### P3-01: FTS5 Query Injection in Notes Search

**File:** `app/notes/routes.py`, line 185; `app/search/routes.py`, lines 46-47, 132-133
**Issue:** User input from the search query is passed directly to SQLite FTS5 `MATCH`
clause. While this is not SQL injection (the `?` parameterization still applies), FTS5
has its own query syntax (`AND`, `OR`, `NOT`, `NEAR`, `*`, `"phrase"`). A user can
craft FTS5 operator strings to alter the search behavior (e.g., `*` to match all
records, or `NOT important` to exclude results).

The search route in `search/routes.py` already has a try/except fallback for invalid
FTS5 syntax, which is good. The notes search route in `notes/routes.py` does not have
this fallback.

**Impact:** Unexpected search results; potential 500 error on malformed FTS5 input in
the notes search endpoint.

**Remediation:** Add the same try/except fallback to `notes/routes.py:search_notes()`
that `search/routes.py` already uses. Consider sanitizing FTS5 special characters from
user input by quoting the term: `f'"{query}"'`.

---

### P3-02: CSV Export Exposes All Columns Including Timestamps

**Files:**
- `app/reports/routes.py`, line 370: `f"SELECT * FROM {table}"`
- `app/settings/routes.py`, line 259: `f"SELECT * FROM {table}"`

**Issue:** The CSV export uses `SELECT *` and dumps all columns. While the table name
is validated against a whitelist (`EXPORT_MODULES`), so there is no SQL injection, the
export includes internal fields like `created_at`, `updated_at`, and all raw IDs. The
`user` table is not in the whitelist, so password hashes are not exposed. However, the
`settings/routes.py` export applies CSV formula injection sanitization via
`_sanitize_csv()`, while the `reports/routes.py` export does not.

**Impact:** Missing formula injection protection on the reports CSV export path.
Internal metadata exposure (low risk).

**Remediation:** Apply `_sanitize_csv()` to the reports export path as well, or
consolidate to a single export endpoint.

---

### P3-03: No Password Complexity Rules Beyond Length

**File:** `app/auth/routes.py`, line 56
**Issue:** Password validation only checks `len(password) < 8`. There is no check for
character diversity (uppercase, lowercase, digit, special character). A password of
`aaaaaaaa` passes validation.

**Impact:** Weak passwords are allowed, increasing brute-force risk.

**Remediation:** Add basic complexity checks or use a password strength library like
`zxcvbn`. At minimum, require at least one letter and one digit.

---

### P3-04: No Account Lockout or Login Rate Limiting

**File:** `app/auth/routes.py`, `login()` function
**Issue:** Failed login attempts have no counter and no lockout mechanism. An attacker
can make unlimited brute-force login attempts.

**Impact:** Credential brute-forcing.

**Remediation:** Track failed login attempts per IP or per email in a table or cache.
Lock out after 5-10 failed attempts for 15 minutes. Consider adding `flask-limiter`
for rate limiting.

---

### P3-05: `bcrypt` in Requirements but Not Used

**File:** `command-center/requirements.txt`, line 3
**Issue:** The `bcrypt>=4.0` package is listed as a dependency but is never imported or
used anywhere. The application uses `werkzeug.security.generate_password_hash` and
`check_password_hash`, which by default uses `scrypt` (Werkzeug 3.x) or `pbkdf2:sha256`
(Werkzeug 2.x). Both are acceptable.

**Impact:** No security impact -- this is a dead dependency. But it suggests the
developers may have intended to use bcrypt and forgot, or switched implementations.

**Remediation:** Either remove `bcrypt` from requirements.txt or explicitly configure
werkzeug to use it: `generate_password_hash(password, method='pbkdf2:sha256')`.

---

## Security Requirements Checklist

| Requirement | Status | Notes |
|---|---|---|
| All inputs validated and sanitized | PARTIAL | Money inputs lack negative-value checks; FTS5 input unsanitized |
| No hardcoded secrets or credentials | PASS | `SECRET_KEY` falls back to `secrets.token_hex(24)` -- OK for dev |
| Proper authentication on all endpoints | PASS | All non-auth routes use `@setup_required` which implies `login_required` |
| SQL queries use parameterization | PASS | All queries use `?` placeholders; ORDER BY uses whitelist |
| XSS protection implemented | PASS | Jinja2 autoescaping enabled; no `|safe` or `Markup()` usage found |
| HTTPS enforced | FAIL | No `SESSION_COOKIE_SECURE`, no HSTS header |
| CSRF protection enabled | PARTIAL | Global `CSRFProtect` active, but auth templates have broken CSRF token output |
| Security headers configured | FAIL | No security headers set at all |
| Error messages don't leak info | PARTIAL | Debug mode hardcoded to True in run.py |
| Dependencies up-to-date | PASS | Flask >=3.0, Flask-WTF >=1.2 (current) |

---

## Risk Matrix

### Critical / P1

| ID | Finding | Exploitability | Impact |
|---|---|---|---|
| P1-01 | Session fixation on login | Medium (requires cookie injection) | High (full account takeover) |
| P1-02 | No multi-tenant data isolation | High (just enumerate IDs) | Critical (full data breach) |
| P1-03 | Open redirect via `next` param | High (trivial crafted URL) | Medium (phishing) |
| P1-04 | Broken CSRF on auth forms | High (missing hidden input) | High (login/register CSRF) |
| P1-05 | Unprotected registration | High (no barriers) | High (combined with P1-02) |

### High / P2

| ID | Finding | Exploitability | Impact |
|---|---|---|---|
| P2-01 | Missing SESSION_COOKIE_SECURE | Medium (network sniffing) | High (session hijack) |
| P2-02 | No security response headers | Low (defense-in-depth) | Medium (clickjacking) |
| P2-03 | Transaction boundary break | Low (race condition) | Low (data inconsistency) |
| P2-04 | Uncaught ValueError in settings | Low (crafted input) | Low (500 error, info leak) |
| P2-05 | Registration race condition | Low (timing window) | Low (500 error) |
| P2-06 | Negative money values accepted | Medium (crafted form) | Medium (data corruption) |
| P2-07 | Debug mode hardcoded | High if network-exposed | Critical (RCE via debugger) |

### Low / P3

| ID | Finding | Exploitability | Impact |
|---|---|---|---|
| P3-01 | FTS5 query syntax injection | Low (unexpected results) | Low (info disclosure) |
| P3-02 | CSV formula injection (reports) | Low (requires Excel open) | Low (client-side) |
| P3-03 | Weak password policy | Medium (brute force) | Medium (account compromise) |
| P3-04 | No login rate limiting | Medium (automated attack) | Medium (brute force) |
| P3-05 | Unused bcrypt dependency | None | None (dead code) |

---

## Remediation Roadmap

### Immediate (before any deployment)

1. **P1-04:** Fix CSRF tokens in auth templates (5-minute fix, 3 files)
2. **P1-01:** Add `session.clear()` before setting `user_id` on login/register (5-minute fix)
3. **P2-07:** Remove hardcoded `debug=True` in run.py (2-minute fix)
4. **P1-05:** Lock registration after first user (10-minute fix)

### Before internet-facing deployment

5. **P1-02:** Add `user_id` to all data tables and scope all queries (large refactor)
6. **P1-03:** Validate redirect targets as same-origin (15-minute fix)
7. **P2-01:** Set `SESSION_COOKIE_SECURE = True` (1-minute fix)
8. **P2-02:** Add security response headers (10-minute fix)
9. **P2-06:** Add negative-value validation to money inputs (20-minute fix)

### Hardening

10. **P2-04:** Add try/except to settings form handlers (10-minute fix)
11. **P2-05:** Handle registration race condition (10-minute fix)
12. **P3-03:** Strengthen password policy (15-minute fix)
13. **P3-04:** Add login rate limiting with flask-limiter (30-minute fix)
14. **P3-01:** Add FTS5 input sanitization (10-minute fix)
15. **P3-02:** Apply CSV sanitization to reports export (5-minute fix)

---

## What Was NOT Found (Positive Signals)

These are areas that were explicitly checked and found to be secure:

- **SQL Injection:** All 100+ queries use parameterized statements with `?` placeholders.
  ORDER BY columns use a whitelist (`_safe_order`). No string concatenation in SQL contexts.
  The `f"SELECT * FROM {table}"` in CSV export is validated against `EXPORT_MODULES` whitelist.

- **XSS:** Zero uses of `|safe` filter or `Markup()` in the entire codebase. Jinja2's
  autoescaping handles all template output. The FTS5 `snippet()` call with `<mark>` tags
  could theoretically inject HTML, but the search results template uses `{{ note['content']|truncate(100) }}`
  which autoescapes the content.

- **Password Hashing:** Uses `werkzeug.security.generate_password_hash` (defaults to
  scrypt in Werkzeug 3.x) -- this is a strong, modern choice.

- **CSRF Coverage:** CSRFProtect is initialized globally in `__init__.py`. All POST
  forms (except the three auth templates noted in P1-04) include the hidden CSRF token
  field correctly.

- **Auth Decorator Coverage:** Every single route in every non-auth blueprint uses
  `@setup_required`, which chains into `login_required`. No unprotected routes were found.

- **Logout:** Uses `session.clear()` with a POST-only endpoint -- correct.

- **Error Messages:** Login failure returns a generic "Invalid email or password" without
  distinguishing between nonexistent email and wrong password (good practice).

- **CSV Export Safety:** The settings export path includes `_sanitize_csv()` to prevent
  formula injection (leading `=`, `+`, `-`, `@` characters are escaped).

---

## Feed-Forward

- **Hardest decision:** Whether to rate P1-02 (no user_id scoping) as critical. For a
  strictly single-user-per-instance deployment, it is by design. But the codebase has
  full user registration and login -- which implies multi-user capability. Rated as P1
  because the code says multi-user but the data model says single-user.

- **Rejected alternatives:** Considered rating the debug=True as P1, but it only applies
  to the `run.py` entry point (not the WSGI entry point a production server would use).
  Kept as P2-07.

- **Least confident:** The auth template CSRF finding (P1-04). Flask-WTF might have
  a mode where `{{ csrf_token() }}` auto-generates the full input tag. I checked the
  Flask-WTF documentation and confirmed: `csrf_token()` returns only the token string.
  The `hidden_tag()` method on WTF forms generates the full input, but that method is
  only available on Flask-WTF Form objects, not the global `csrf_token()` function.
  These templates use raw HTML forms (not WTF Form objects), so the bare `{{ csrf_token() }}`
  outputs only the token text, not a hidden input.
