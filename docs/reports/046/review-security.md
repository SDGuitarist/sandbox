# Security Audit: Invoice & CRM Flask Application

**Date:** 2026-05-19
**Scope:** Full application -- 12 blueprints, ~6,000 lines, Flask + SQLite + Jinja2
**Auditor:** Security Sentinel (Claude Opus 4.6)

---

## Executive Summary

The application has a **solid security baseline**. SQL injection, CSRF, XSS, and password hashing are all handled correctly at the framework level. However, the audit uncovered **3 P1 findings** related to authorization gaps that could allow cross-tenant data manipulation in a multi-user deployment. These are critical because the application handles money (invoices, payments).

**Risk Rating: MEDIUM** -- no remote code execution or data exfiltration vectors, but authorization gaps in a financial application are serious.

---

## Findings

### P1 -- Must Fix

#### P1-1: IDOR on `client_id` in Invoice Create/Edit (Authorization Bypass)

**Severity:** HIGH
**Files:**
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/invoices/routes.py` lines 137, 366
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/invoices/routes.py` (edit path, same pattern)

**Description:** When creating or editing an invoice, `client_id` is taken directly from `request.form.get('client_id', type=int)` and inserted into the database without verifying that the client belongs to the current `session['user_id']`. An attacker (User A) can craft a POST request with User B's `client_id`, linking their invoice to another user's client.

**Impact:** Cross-tenant data association. User A's invoice would reference User B's client. When User A views the invoice, the `view_invoice` route fetches the client record by `id` alone (line 270-273) without a `user_id` check:

```python
client = db.execute(
    "SELECT * FROM clients WHERE id = ?",
    (invoice['client_id'],)
).fetchone()
```

This leaks User B's client name, company, address, email, and phone to User A.

**Fix:** Before inserting, verify client ownership:

```python
client_check = db.execute(
    "SELECT id FROM clients WHERE id = ? AND user_id = ?",
    (client_id, user_id)
).fetchone()
if not client_check:
    flash('Invalid client.', 'danger')
    return redirect(url_for('invoices.create_invoice'))
```

Also fix `view_invoice` line 270 to add `AND user_id = ?` to the client lookup.

---

#### P1-2: Invoice Status Bypass via Payment Recording

**Severity:** HIGH
**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/payments/routes.py` lines 9-69

**Description:** The `create_payment` route does not check the invoice's current status before accepting a payment. The invoice status machine defines `ALLOWED_TRANSITIONS` in the invoices blueprint, but the payments route bypasses it entirely. A user can:

1. Create an invoice (status: `draft`)
2. Record a payment against it while it is still in `draft` status
3. The payment auto-marks it as `paid` (line 48-52), skipping `draft -> sent -> paid`

This violates the application's own business rules. A draft invoice that has never been sent to the client should not be payable.

**Impact:** Business logic integrity violation. In a real accounting workflow, this means invoices could be marked paid without ever being issued, creating audit trail gaps.

**Fix:** Add a status guard at the top of `create_payment`:

```python
if invoice['status'] not in ('sent', 'viewed', 'overdue'):
    flash('Payments can only be recorded on sent, viewed, or overdue invoices.', 'danger')
    return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
```

---

#### P1-3: No Brute-Force Protection on Login

**Severity:** HIGH
**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/auth/routes.py` lines 10-24

**Description:** The login endpoint has no rate limiting, account lockout, or progressive delay mechanism. An attacker can make unlimited login attempts against any email address. The generic error message ("Invalid email or password") is good practice for preventing user enumeration, but without rate limiting, automated password guessing is trivial.

**Impact:** Credential compromise via brute force. Since this is a financial application, a compromised account exposes all invoices, payments, and client data.

**Fix:** Add `flask-limiter` to the project:

```python
from flask_limiter import Limiter
limiter = Limiter(key_func=get_remote_address)

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    ...
```

Alternatively, implement a simple counter in the session or database that locks after N failed attempts.

---

### P2 -- Should Fix

#### P2-1: Recurring Settings Route Lacks Server-Side Validation

**Severity:** MEDIUM
**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/recurring/routes.py` lines 89-103

**Description:** The `set_recurring` POST handler reads `recurrence_interval` and `next_recurrence_date` directly from `request.form.get()` without using a WTForms form or any server-side validation. Unlike every other POST route in the application (which all use FlaskForm), this one processes raw form data.

Problems:
- `recurrence_interval` is not validated against the allowed set (`weekly`, `monthly`, `quarterly`, `annually`). The database has a CHECK constraint that will reject invalid values, but the user gets a 500 error instead of a friendly message.
- `next_recurrence_date` is not validated as a date. Garbage input goes into the database (SQLite stores it as TEXT, no format check).
- No CSRF protection via FlaskForm (though `csrf_token` is manually included in the template, CSRFProtect will validate it globally, so this is actually OK -- but it is inconsistent with the pattern).

**Fix:** Create a `RecurringForm` FlaskForm class with `SelectField` for interval and `DateField` for next date, matching the pattern used everywhere else.

---

#### P2-2: Negative Amounts Accepted in Invoice Line Items

**Severity:** MEDIUM
**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/invoices/routes.py` lines 179-210

**Description:** Invoice line items accept `quantity`, `unit_price`, and `tax_rate` as raw `float()` conversions with no minimum value check. A user can submit:
- Negative quantities (e.g., `-10`)
- Negative unit prices (e.g., `-500.00`)
- Negative tax rates (e.g., `-15`)

This results in invoices with negative totals. While credit memos are a legitimate use case, they should be explicit, not an accidental side effect of missing validation.

The same issue exists in the edit path (lines 390-425).

**Fix:** Add bounds checking after parsing:

```python
if qty <= 0 or up_cents < 0 or tr < 0:
    flash('Quantity must be positive; price and tax rate must be non-negative.', 'danger')
    return redirect(url_for('invoices.create_invoice'))
```

---

#### P2-3: Logout Via GET Request (CSRF-Susceptible)

**Severity:** MEDIUM
**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/auth/routes.py` lines 50-53

**Description:** The logout route is a plain GET:

```python
@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
```

An attacker can force a logged-in user to log out by embedding `<img src="/auth/logout">` on any page the user visits. While logout CSRF is lower severity than action CSRF, it can be used for denial-of-service or as part of a session fixation chain.

**Fix:** Change to POST with CSRF token:

```python
@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
```

Update the nav template to use a form instead of a link.

---

#### P2-4: Session Not Regenerated After Login (Session Fixation Risk)

**Severity:** MEDIUM
**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/auth/routes.py` lines 20-21

**Description:** After successful authentication, the code sets `session['user_id']` but does not regenerate the session ID. If an attacker can fixate a session cookie before the user logs in (e.g., via a subdomain or XSS on a related domain), the attacker's pre-set session ID becomes authenticated.

```python
if user and check_password_hash(user['password_hash'], password):
    session['user_id'] = user['id']  # No session regeneration
```

**Fix:** Clear and regenerate the session before setting user_id:

```python
if user and check_password_hash(user['password_hash'], password):
    session.clear()
    session['user_id'] = user['id']
    return redirect(url_for('dashboard.index'))
```

Flask's default session implementation (signed cookies) makes traditional session fixation harder, but `session.clear()` before login is still best practice.

---

#### P2-5: No Cookie Security Flags Configured

**Severity:** MEDIUM
**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/__init__.py`

**Description:** The application does not configure session cookie security attributes. Flask defaults:
- `SESSION_COOKIE_HTTPONLY` = True (good, default)
- `SESSION_COOKIE_SECURE` = False (bad for production -- cookies sent over HTTP)
- `SESSION_COOKIE_SAMESITE` = None (should be `Lax` or `Strict`)
- `PERMANENT_SESSION_LIFETIME` = 31 days (very long for a financial app)

**Fix:** Add to `create_app()`:

```python
app.config['SESSION_COOKIE_SECURE'] = not app.debug
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
```

---

#### P2-6: `catalog_item_id` Not Validated for Ownership

**Severity:** MEDIUM
**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/invoices/routes.py` lines 196-200

**Description:** When creating or editing an invoice, submitted `catalog_item_ids[]` values are stored in `invoice_line_items` without verifying that the catalog item belongs to the current user. An attacker can associate another user's catalog items with their invoice line items. The impact is limited since the catalog_item_id is only a reference (the description and price are stored independently on the line item), but it violates data isolation.

**Fix:** If `cat_id` is provided, verify ownership before storing:

```python
if cat_id:
    cat_check = db.execute(
        "SELECT id FROM catalog_items WHERE id = ? AND user_id = ?",
        (cat_id, user_id)
    ).fetchone()
    if not cat_check:
        cat_id = None
```

---

### P3 -- Nice to Have

#### P3-1: Password Policy Is Minimal

**Severity:** LOW
**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/auth/forms.py` line 14

**Description:** The registration form requires `Length(min=6)` for passwords. For a financial application, this is weak. No requirements for complexity (uppercase, digit, special character).

**Fix:** Add a custom validator or increase minimum to 8+ with complexity requirements.

---

#### P3-2: CSV Export Content-Disposition Uses Unvalidated Input

**Severity:** LOW
**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/reports/routes.py` line 173

**Description:** The `report_type` parameter goes into the `Content-Disposition` header:

```python
headers={'Content-Disposition': f'attachment; filename={report_type}.csv'}
```

The `report_type` is constrained to four known values by the if/elif chain (lines 143-167), so this is not exploitable in practice. However, the catch-all `else` returns before the header is set. If the code were refactored and the guard removed, this could become a header injection vector.

**Fix:** Whitelist explicitly:

```python
VALID_REPORTS = {'revenue_by_month', 'revenue_by_client', 'aging', 'forecast'}
if report_type not in VALID_REPORTS:
    return "Invalid report type", 404
```

---

#### P3-3: SECRET_KEY Falls Back to Random Value

**Severity:** LOW
**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/__init__.py` line 11

**Description:** `app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(24))`. If `SECRET_KEY` is not in the environment, a new random key is generated on each process restart. This means all sessions are invalidated on restart, which is annoying but not a security hole. However, if running multiple workers (e.g., gunicorn with multiple processes), each worker gets a different key, causing session validation failures.

**Fix:** In production, always require `SECRET_KEY` from the environment:

```python
if not app.debug:
    assert os.environ.get('SECRET_KEY'), "SECRET_KEY must be set in production"
```

---

#### P3-4: `delete_invoice` Does Not Check Status

**Severity:** LOW
**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/invoices/routes.py` lines 578-597

**Description:** Any invoice can be deleted regardless of status, including `paid` invoices with payment records. While the CASCADE delete handles foreign keys, deleting a paid invoice destroys the audit trail. This is more of a business logic concern than a security issue.

**Fix:** Block deletion of paid invoices, or implement soft delete.

---

## Security Checklist Summary

| Control | Status | Notes |
|---|---|---|
| SQL Injection | PASS | All queries use `?` parameterization. The two f-string queries in `clients/routes.py` use `?` placeholders dynamically (safe pattern). |
| CSRF Protection | PASS | `CSRFProtect()` is initialized globally. All forms include `hidden_tag()` or manual `csrf_token`. |
| XSS Protection | PASS | Jinja2 autoescaping is on (default for `.html`). No `|safe` or `Markup()` usage found anywhere. |
| Password Hashing | PASS | Uses `werkzeug.security.generate_password_hash` / `check_password_hash` (PBKDF2 by default). |
| Authentication Gates | PASS | `@login_required` decorator on all non-auth routes. Verified all 12 blueprints. |
| IDOR / Authorization | FAIL | P1-1: `client_id` not ownership-checked in invoice create/edit. P2-6: `catalog_item_id` not checked. |
| Input Validation | PARTIAL | WTForms used consistently except recurring settings (P2-1). Negative amounts not blocked (P2-2). |
| Business Logic | FAIL | P1-2: Payments bypass invoice status machine. |
| Brute Force Protection | FAIL | P1-3: No rate limiting on login. |
| Session Security | PARTIAL | P2-4: No session regeneration. P2-5: No cookie security flags. |
| Secrets Management | PASS | SECRET_KEY uses `secrets.token_hex()` fallback. No hardcoded credentials. |
| Dependency Security | NOT TESTED | No `requirements.txt` or `pyproject.toml` was audited. |

---

## Remediation Priority

1. **P1-1** (IDOR on client_id) -- Fix immediately. 5-line change per route.
2. **P1-2** (Status bypass via payments) -- Fix immediately. 3-line guard.
3. **P1-3** (No brute force protection) -- Add `flask-limiter`. Small dependency.
4. **P2-4** (Session fixation) -- Add `session.clear()` before login. 1-line fix.
5. **P2-5** (Cookie flags) -- Add 3 config lines.
6. **P2-2** (Negative amounts) -- Add bounds check. 3-line fix.
7. **P2-1** (Recurring validation) -- Create WTForms form. Small refactor.
8. **P2-3** (GET logout) -- Change to POST form. Template + route change.
9. **P2-6** (catalog_item_id ownership) -- Add check. 4-line fix.
10. **P3-**** -- Address as time permits.

---

## What Was NOT Found (Positive Signals)

- No SQL injection vectors. Every single `db.execute()` call (checked all 100+) uses parameterized queries.
- No XSS vectors. Zero uses of `|safe` or `Markup()`. Jinja2 autoescaping covers all templates.
- No hardcoded secrets, API keys, or credentials in source.
- CSRF is comprehensively applied -- every POST form has a token.
- All routes correctly scope data queries to `session['user_id']` (with the specific exceptions noted in P1-1 and P2-6).
- The `ALLOWED_TRANSITIONS` status machine is well-designed and correctly enforced in the status update route.
- Database schema uses CHECK constraints as a defense-in-depth layer.
- Foreign keys are ON with CASCADE, preventing orphan records.
