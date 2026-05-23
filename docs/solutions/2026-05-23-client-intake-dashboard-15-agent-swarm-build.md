---
title: Client Intake Dashboard -- 15-Agent Swarm Build
date: 2026-05-23
run_id: "058"
app: intake-dashboard
framework: Flask + SQLite + Jinja2 + Bootstrap 5
agents: 15
smoke_tests: 36
p1_found: 10
p1_fixed: 9
p1_deferred: 1
p2_deferred: 11
p3_deferred: 15
tags: [swarm, flask, intake-form, admin-dashboard, csrf, rate-limiting]
---

# Client Intake Dashboard -- 15-Agent Swarm Build

## Problem

Build a client intake dashboard for the Amplify AI consulting business's $500
Audit tier. Public workshop attendees submit an intake form. Admin (Alex)
reviews submissions, creates bottleneck assessments, and decides whether to
schedule a paid audit.

## Solution

15-agent swarm build producing a Flask + SQLite + Jinja2 + Bootstrap 5 app
with 6 blueprints, 3 models, 12 routes, and 36 smoke tests.

### Architecture

- **Public side:** Intake form with 11 fields, email validation, honeypot spam
  filter, rate limiting (5/min/IP)
- **Admin side:** Dashboard with status counts, submission list with filtering,
  detail view with notes/status/assessment management, audit-fit toggle
- **Auth:** Single admin user, password hashed with Werkzeug, session-based with
  CSRF protection via Flask-WTF
- **Database:** SQLite with WAL mode, foreign keys, busy timeout. Three tables:
  submissions, assessments (1:1), notes (1:many)

### Key Design Decisions

1. **4 blueprints on same url_prefix:** submissions, detail, status, and
   assessments all share `/admin/submissions`. Unusual but necessary for clean
   agent ownership boundaries. No route shadowing because each blueprint defines
   distinct path patterns.

2. **BEGIN IMMEDIATE for status changes:** `update_status` uses explicit
   `BEGIN IMMEDIATE` with try/except/ROLLBACK to prevent TOCTOU races on
   terminal-state enforcement. Other write functions use simple single-statement
   commits.

3. **Module-level extensions:** `csrf` and `limiter` are module-level in
   `__init__.py` so blueprints can import them directly.

## Lessons

### L1: XSS in Jinja2 custom filters requires explicit escaping

The `status_badge` filter used an f-string with `Markup()` wrapping. The status
value was not escaped before interpolation, allowing XSS if a malicious status
string were injected. Fix: use `markupsafe.escape()` on the status value before
embedding it in the HTML string.

**Why this matters:** Jinja2 auto-escapes template variables, but inside custom
filters using `Markup()`, auto-escaping is bypassed by design. Every filter
that returns `Markup()` must manually escape its inputs.

### L2: SECRET_KEY must never have a dev fallback in production-facing code

The spec prescribed `os.environ.get('SECRET_KEY', 'dev-fallback-insecure')`.
Review correctly flagged this -- if the env var is missing, the app runs with a
known secret. Fix: raise `RuntimeError` if SECRET_KEY is not set, matching the
pattern already used for ADMIN_PASSWORD.

### L3: session.clear() vs session.pop() on logout

Using `session.pop('logged_in', None)` leaves other session keys intact,
creating a potential session fixation vector if an attacker can inject keys
before authentication. `session.clear()` removes everything. Use `session.clear()`
for logout.

### L4: Flow-trace reviewer catches cross-file bugs that single-file reviewers miss

The `audit_fit` -> `is_audit_fit` key mismatch was invisible to single-file
reviewers because each file was internally consistent. The column name in
`schema.sql` was `is_audit_fit`, the model function was `toggle_audit_fit`,
and the template accessed `submission['audit_fit']`. The flow-trace reviewer
traced the data path across all three files and caught the mismatch.

**Impact:** This was a crash-level P1 -- every detail page would 500.

### L5: Assessment summary validation was missing

The spec listed assessment fields as optional (0-5000 chars), but review
determined that an assessment without a summary is meaningless. Added required
validation for the summary field.

### L6: Same-status transitions should be rejected

Without a same-status check, clicking "reviewed" when the submission is already
"reviewed" would update `updated_at` without changing anything meaningful.
Added a guard: if `new_status == current_status`, flash error and redirect.

## What Went Well

- 15/15 agents merged with 0 conflicts
- 36/36 smoke tests passed on first assembly
- Spec had all 6 mandatory sections (Export Names, Cross-Boundary Wiring,
  Input Validation, Coordinated Behaviors, Transaction Contracts, Authorization
  Matrix)
- Blueprint registration order (auth -> intake -> dashboard -> submissions ->
  detail -> status -> assessments) had no route shadowing issues despite
  feed-forward concern

## What Went Wrong

- 10 P1 findings across 5 review agents -- higher than recent builds
- The `is_audit_fit` key mismatch was a spec-to-template inconsistency that
  the spec-consistency-checker should have caught but didn't (the column name
  was correct in schema.sql and models, but the template section didn't
  prescribe the exact access key)
- 1 TOCTOU P1 deferred because no delete endpoint exists (the outer 404 guard
  in `change_status` reads the submission outside the lock, then `update_status`
  re-reads inside `BEGIN IMMEDIATE`)

## Feed-Forward

- **Hardest decision:** Whether to fix the TOCTOU gap in status routes. Deferred
  because no delete endpoint exists, so the race condition cannot be triggered.
- **Rejected alternatives:** Eliminating the outer 404 guard entirely (would
  change error messages for legitimate 404s).
- **Least confident:** The 11 P2 and 15 P3 deferred findings. Several P2s
  (pagination, JSON API, query optimization) would be needed for production use.
