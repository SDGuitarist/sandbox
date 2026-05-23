# Flow Trace Review -- Client Intake Dashboard

**Project:** `/Users/alejandroguillen/Projects/sandbox/intake-dashboard/`
**Date:** 2026-05-22
**Flows traced:** 4
**Reviewer:** cross-flow data integrity agent

---

## Summary

| Flow | Files Crossed | Result |
|------|---------------|--------|
| 1. Intake Submission | form.html -> intake/routes.py -> submissions.py -> schema.sql | PASS |
| 2. Status Change | detail/show.html -> status/routes.py -> submissions.py | FAIL (P1) |
| 3. Assessment Create/Update | assessments/form.html -> assessments/routes.py -> assessments.py | PASS |
| 4. Auth | login.html -> auth.py -> session -> login_required -> admin routes | PASS |

---

### Flow 1: Intake Submission (form.html -> intake/routes.py -> submissions.py -> schema.sql)

**Data traced:** 11 form fields created in `form.html`, validated and collected in `intake/routes.py`, written to the `submissions` table via `submissions.py:create_submission`, persisted in `schema.sql`.

**Storage step:** `submissions` table, one row per submission. `create_submission` commits internally via `conn.commit()` at `submissions.py:43`.

**Code paths checked:**
- Happy path: all 11 fields present and valid
- Honeypot path: early redirect before any DB write (correct)
- Validation failure path: `flash()` and re-render, no DB write attempted (correct)
- Email normalization: `valid.normalized` overwrites the raw input before storage (correct)

**Field-by-field verification (form field name -> route collection -> INSERT column -> schema column):**

| Form `name=` | Collected in routes.py | INSERT parameter position | schema.sql column |
|---|---|---|---|
| `contact_name` | `fields['contact_name']` | position 1 | `contact_name TEXT NOT NULL` |
| `email` | `fields['email']` | position 2 | `email TEXT NOT NULL` |
| `business_name` | `fields['business_name']` | position 3 | `business_name TEXT NOT NULL` |
| `business_type` | `fields['business_type']` | position 4 | `business_type TEXT NOT NULL` |
| `team_size` | `fields['team_size']` | position 5 | `team_size TEXT NOT NULL` |
| `current_workflows` | `fields['current_workflows']` | position 6 | `current_workflows TEXT NOT NULL` |
| `pain_points` | `fields['pain_points']` | position 7 | `pain_points TEXT NOT NULL` |
| `tools_used` | `fields['tools_used']` | position 8 | `tools_used TEXT NOT NULL` |
| `goals` | `fields['goals']` | position 9 | `goals TEXT NOT NULL` |
| `urgency` | `fields['urgency']` | position 10 | `urgency TEXT NOT NULL` |
| `submitter_notes` | `fields['submitter_notes']` | position 11 (via `data.get`) | `submitter_notes TEXT NOT NULL DEFAULT ''` |

All 11 fields align correctly across all three files. The positional parameter order in `submissions.py:36-41` matches the INSERT column list exactly.

**Return value:** `create_submission` returns the new `submission_id` (int). At `intake/routes.py:67` the call is written as a bare statement: `create_submission(conn, fields)`. The return value is discarded. This is acceptable because the intake route redirects to a static thank-you page with no need for the ID. No data is lost.

**Commit coverage:** `conn.commit()` is called unconditionally inside `create_submission` before returning. The route has no try/except that could swallow an exception and return 200 without committing -- an unhandled exception bubbles up to Flask's error handler. Commit coverage is complete.

**Result:** PASS

---

### Flow 2: Status Change (detail/show.html -> status/routes.py -> submissions.py)

**Data traced:** `new_status` string selected in the `<select>` in `detail/show.html`, POSTed to `status/routes.py:change_status`, passed to `submissions.py:update_status` which enforces terminal-state rules and writes the new status to the DB.

**Storage step:** `submissions` table, `status` column. `update_status` uses `BEGIN IMMEDIATE` + `conn.commit()` on success, or `conn.rollback()` on terminal-state or exception.

**Code paths checked:**
- Valid non-terminal status: `update_status` returns True, `conn.commit()` fires
- Terminal status submitted: `update_status` returns False, `conn.rollback()` fires, flash warning shown
- Invalid status string: rejected at `status/routes.py:17-19` before any DB write
- Submission not found (outer guard): `status/routes.py:13-15` aborts 404 before model call
- Submission not found (inner guard, inside BEGIN IMMEDIATE): `submissions.py:103` catches None, rolls back

**Terminal-state enforcement analysis:**

The `update_status` function correctly re-reads the current status inside the `BEGIN IMMEDIATE` lock at `submissions.py:99-103`. This means the enforcement is race-safe -- no other writer can change the status between the read and the UPDATE.

**FAIL -- P1: TOCTOU gap in the outer 404 guard creates a double-read without synchronization.**

The route at `status/routes.py:12-15` reads the submission via `get_submission` (a plain SELECT, no lock) to do a 404 guard check. Then `update_status` at `submissions.py:98` opens `BEGIN IMMEDIATE` and re-reads the same row. This means the submission is read twice: once outside any lock and once inside the exclusive lock.

This creates a window: if the submission is hard-deleted between the outer `get_submission` call and the inner `BEGIN IMMEDIATE` read, the outer call returns a row (no 404), the inner call returns None, `update_status` returns False, and the route flashes "Cannot change status of completed/declined/archived submission" -- a misleading error message. The submission is gone but the user is told it is in a terminal state.

In the current schema there is no admin deletion endpoint, so this gap cannot be triggered at runtime today. However, the invariant is fragile: any future deletion feature would expose this bug. Because the false message is actively misleading and the fix is trivial, this is classified as P1.

**File:** `/Users/alejandroguillen/Projects/sandbox/intake-dashboard/app/blueprints/status/routes.py:12-20`

**Impact:** If a submission is deleted between the outer 404 check and the inner BEGIN IMMEDIATE read, the user receives "Cannot change status of completed/declined/archived submission" instead of a 404. The error is incorrect and the submission no longer exists.

**Fix:** Remove the outer `get_submission` call from `change_status`. Let `update_status` own the "not found" check entirely (it already handles `row is None` at `submissions.py:103`). Return a distinct value (e.g., `None` or raise a custom exception) so the route can distinguish "not found" from "terminal state" and respond with the correct HTTP status or flash message.

**Result:** FAIL

---

### Flow 3: Assessment Create/Update (assessments/form.html -> assessments/routes.py -> assessments.py)

**Data traced:** 6 assessment fields (`summary`, `bottlenecks`, `root_causes`, `next_steps`, `audit_fit_recommendation`, `admin_notes`) submitted from `assessments/form.html`, collected in `assessments/routes.py:assessment_form`, dispatched to either `create_assessment` or `update_assessment` in `assessments.py`.

**Storage step:** `assessments` table. Both `create_assessment` (INSERT) and `update_assessment` (UPDATE) commit internally.

**Create vs update routing logic:**
- `assessments/routes.py:17` fetches `assessment = get_assessment_by_submission(conn, submission_id)` before the POST branch.
- On POST, if `assessment` is truthy, `update_assessment(conn, assessment['id'], data)` is called. If falsy, `create_assessment(conn, submission_id, data)` is called.
- The `assessments` table has `UNIQUE` on `submission_id`, so a duplicate INSERT would raise an IntegrityError. The route correctly prevents this by checking for an existing assessment before choosing the code path.

**Field-by-field verification (form `name=` -> routes.py key -> model parameter -> schema column):**

| Form `name=` | Collected in routes.py | Passed to model | schema.sql column |
|---|---|---|---|
| `summary` | `data['summary']` | `data.get('summary', '')` | `summary TEXT NOT NULL DEFAULT ''` |
| `bottlenecks` | `data['bottlenecks']` | `data.get('bottlenecks', '')` | `bottlenecks TEXT NOT NULL DEFAULT ''` |
| `root_causes` | `data['root_causes']` | `data.get('root_causes', '')` | `root_causes TEXT NOT NULL DEFAULT ''` |
| `next_steps` | `data['next_steps']` | `data.get('next_steps', '')` | `next_steps TEXT NOT NULL DEFAULT ''` |
| `audit_fit_recommendation` | `data['audit_fit_recommendation']` | `data.get('audit_fit_recommendation', '')` | `audit_fit_recommendation TEXT NOT NULL DEFAULT ''` |
| `admin_notes` | `data['admin_notes']` | `data.get('admin_notes', '')` | `admin_notes TEXT NOT NULL DEFAULT ''` |

All 6 fields align across all three files. The UPDATE statement in `assessments.py:72-81` uses `WHERE id = ?` with `assessment_id` (the assessment's own primary key), not `submission_id`. The caller passes `assessment['id']` at `assessments/routes.py:29`, which is correct.

**Code paths checked:**
- Create path (no existing assessment): `create_assessment` called, INSERT + commit
- Update path (existing assessment): `update_assessment` called, UPDATE + commit
- Submission not found: `abort(404)` before any form processing

**Result:** PASS

---

### Flow 4: Auth (login.html -> auth.py -> session -> login_required -> admin routes)

**Data traced:** `username` and `password` submitted from `login.html`, validated in `auth.py:login`, result stored in `session['logged_in']`, read back by `login_required` decorator in `auth.py:11-17`, which gates all admin blueprint routes.

**Storage step:** Flask server-side session (cookie-backed, signed with `SECRET_KEY`).

**Code paths checked:**
- Valid credentials: `session.clear()` then `session['logged_in'] = True` set, redirect to dashboard
- Invalid credentials: no session mutation, flash error, re-render login
- Already logged in: short-circuit redirect to dashboard at `auth.py:22-23` (avoids double login)
- Logout: `session.pop('logged_in', None)`, redirect to login
- Protected route without session: `login_required` redirects to `auth.login`

**Session key consistency:**
- Written at `auth.py:31`: `session['logged_in'] = True`
- Read at `auth.py:14`: `session.get('logged_in')`
- Key is identical in both places. No mismatch.

**Admin route coverage -- every blueprint route decorated with `@login_required`:**

| Blueprint | Route | Decorated |
|---|---|---|
| `dashboard` | `GET /admin/` | yes |
| `submissions` | `GET /admin/submissions/` | yes |
| `detail` | `GET /admin/submissions/<id>` | yes |
| `detail` | `POST /admin/submissions/<id>/notes` | yes |
| `status` | `POST /admin/submissions/<id>/status` | yes |
| `status` | `POST /admin/submissions/<id>/audit-fit` | yes |
| `assessments` | `GET/POST /admin/submissions/<id>/assessment` | yes |

All admin routes are covered. The public routes (`/intake/`, `/login`, `/logout`, `/health`) are correctly not decorated.

**CSRF coverage:** All POST forms in `login.html`, `detail/show.html`, and `assessments/form.html` include `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`. `flask_wtf.CSRFProtect` is initialized at `__init__.py:30`. Logout uses a POST form (not a GET link), which is correct.

**Result:** PASS

---

### Supplemental Finding: `audit_fit` column name mismatch (P1)

This finding emerged during Flow 2 tracing when checking how the toggle result is displayed.

**Data traced:** The `is_audit_fit` column written by `toggle_audit_fit` in `submissions.py:130`, fetched by `get_submission` via `SELECT *`, then read in `detail/show.html`.

**Bug:** `detail/show.html:16` accesses `submission['audit_fit']` but the column name in `schema.sql:17` is `is_audit_fit`. These are different keys.

**File:** `/Users/alejandroguillen/Projects/sandbox/intake-dashboard/app/templates/detail/show.html:16`

**Impact:** `sqlite3.Row` accessed with an unknown key raises `IndexError` at render time. Every request to the detail page crashes with a 500 error immediately after the assessment section renders. The Audit Fit toggle and badge are completely broken.

**Fix:** Change `submission['audit_fit']` to `submission['is_audit_fit']` at `detail/show.html:16`.

---

## Issues Found

### P1-A: Misleading error on deleted submission during status change

- **File:** `/Users/alejandroguillen/Projects/sandbox/intake-dashboard/app/blueprints/status/routes.py:12-20`
- **Bug:** Double-read of submission row -- outer read outside lock, inner read inside `BEGIN IMMEDIATE`. If submission is deleted between reads, user sees "Cannot change status of terminal submission" instead of 404.
- **Fix:** Eliminate the outer `get_submission` call; let `update_status` return a three-valued result that distinguishes not-found from terminal-state.

### P1-B: `submission['audit_fit']` key mismatch -- column is `is_audit_fit`

- **File:** `/Users/alejandroguillen/Projects/sandbox/intake-dashboard/app/templates/detail/show.html:16`
- **Bug:** Wrong dict key used to read the audit-fit flag. `sqlite3.Row` raises `IndexError` on unknown keys. Every detail page renders as a 500 error.
- **Fix:** Change `submission['audit_fit']` to `submission['is_audit_fit']`.

---

```
STATUS: FAIL -- 4 flows traced, 2 issues found (both P1)
```
