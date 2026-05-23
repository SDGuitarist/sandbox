# Client Intake Dashboard -- Brainstorm

**Date:** 2026-05-22
**Status:** Complete
**Brief:** docs/briefs/2026-05-22-client-intake-dashboard-brief.md

## What We're Building

A Flask + SQLite + Jinja2 + Bootstrap 5 web app for the Amplify AI consulting
business's $500 Audit tier. Public workshop attendees submit an intake form
with business and workflow information. Alex (single admin) reviews submissions,
creates bottleneck assessments, and decides whether to schedule a paid audit.

Two user types:
- **Public:** Submit intake form (no login required)
- **Admin:** Log in, review submissions, add notes, create/edit assessments,
  update status, mark audit-fit

## Why This Approach

### Approach Chosen: Standard Flask Swarm (15-20 agents)

This is a well-defined CRUD app with a public form, admin dashboard, and a
simple status workflow. The sandbox has shipped 10+ Flask swarm builds at this
scale with a proven spec template. No new patterns needed.

**Why not solo?** The brief explicitly requests 15-25 agents. The app has
enough surface area (public form, admin list/detail, assessment CRUD, notes,
status workflow, auth, seed data) to split cleanly across 15-20 agents.

**Why not Express/Node?** Brief says Flask. Sandbox standard stack. All prior
lessons apply directly.

### Rejected Alternative: Embedded JSON Assessments

Storing assessments as a JSON column on submissions would reduce table count
but makes querying, validation, and future reporting harder. A separate
assessments table with FK to submissions is simpler for the admin workflow
and aligns with sandbox patterns.

### Rejected Alternative: Strict State Machine Enforcement

The brief says "admin changes status manually." Enforcing a strict state
machine (only specific transitions allowed) adds complexity. Instead: define
valid transitions in Coordinated Behaviors for UI guidance, but allow any
admin-driven change. Terminal states (declined, completed, archived) are
enforced -- no transitions out of these.

## Key Decisions

### 1. Database Schema (3 tables)

| Table | Purpose |
|-------|---------|
| submissions | Intake form data (11 fields + metadata) |
| assessments | One per submission, FK to submissions, 6 structured fields |
| notes | Multiple per submission, FK to submissions, timestamped |

**Why 3 tables, not 2:** Notes are timestamped, multiple per submission, and
have different access patterns than assessments. Combining them would require
complex filtering.

### 2. Assessment Structure (6 fields, all TEXT)

1. `summary` -- brief overview of the business situation
2. `bottlenecks` -- current-state bottlenecks identified
3. `root_causes` -- likely root causes of bottlenecks
4. `next_steps` -- recommended next steps
5. `audit_fit` -- audit-fit recommendation (TEXT, not boolean -- allows nuance)
6. `admin_notes` -- internal notes visible only to admin

All TEXT columns. No AI generation -- Alex writes these manually. Each
assessment has exactly one submission (1:1 relationship enforced by UNIQUE
constraint on submission_id).

### 3. Status Workflow

```
new -> reviewed -> assessment-ready -> audit-scheduled -> completed
                                                       -> declined
                                    -> declined
         -> declined
new -> archived (skip straight to archive)
```

- `new`: Default on form submit
- `reviewed`: Admin has looked at it
- `assessment-ready`: Assessment created
- `audit-scheduled`: Audit call booked
- `completed`: Audit done
- `declined`: Not a fit
- `archived`: Stored for later, no action

**Terminal states:** declined, completed, archived (no transitions out)
**Enforcement:** Application-level check in status update route. Not a strict
state machine -- admin can move between non-terminal states freely.

### 4. Public Form Security

| Control | Implementation |
|---------|---------------|
| CSRF | Flask-WTF CSRFProtect, `{{ csrf_token() }}` in form |
| Validation | Server-side, all fields required except notes |
| Length caps | name: 100, email: 254, business_name: 200, text fields: 2000 |
| Email | WTForms Email() validator + email-validator package |
| Rate limiting | flask-limiter, 5/minute per IP on submit endpoint |
| Honeypot | Hidden `website` field, CSS display:none, reject if filled |
| Admin protection | @login_required on all /admin/* routes |

### 5. Admin Authentication

- Single admin, session-based
- Username/password from environment variables (ADMIN_USERNAME, ADMIN_PASSWORD)
- bcrypt hash comparison (password hashed at startup if raw)
- Session timeout: 8 hours
- Login page at /login, logout at /logout (POST only for CSRF safety)

### 6. Agent Split (estimated 15-18 agents)

| Agent | Files |
|-------|-------|
| core | app/__init__.py, app/db.py, schema.sql, requirements.txt |
| layout | app/templates/base.html, app/static/style.css |
| auth | app/auth.py, app/templates/auth/ |
| submission_models | app/models/submissions.py |
| assessment_models | app/models/assessments.py |
| note_models | app/models/notes.py |
| intake_routes | app/blueprints/intake/routes.py, app/templates/intake/ |
| submissions_routes | app/blueprints/submissions/routes.py, app/templates/submissions/ |
| assessment_routes | app/blueprints/assessments/routes.py, app/templates/assessments/ |
| notes_routes | app/blueprints/notes/routes.py, app/templates/notes/ |
| status_routes | app/blueprints/status/routes.py |
| dashboard_routes | app/blueprints/dashboard/routes.py, app/templates/dashboard/ |
| filters | app/filters.py |
| seed | seed.py |
| tests | test_smoke.py |

~15 agents. Could split further if routes have many templates, but this is
a clean vertical split. The plan phase will finalize exact boundaries.

### 7. Bootstrap CDN vs Local

Use Bootstrap 5 from CDN (cdn.jsdelivr.net). CSP header must include
`cdn.jsdelivr.net` in script-src and style-src (lesson from GigSheet FC38).

### 8. No Search / No FTS5

MVP has no search feature. Filter by status dropdown only. No FTS5 needed,
so FC36 does not apply.

## Open Questions

None -- all design questions resolved. The plan phase will finalize agent
boundaries, exact route paths, and the full shared interface spec.

## Feed-Forward

- **Hardest decision:** Assessment as a separate table vs JSON column on
  submissions. Chose separate table for queryability and clean CRUD, but it
  adds a table and a model agent. Worth it for the admin workflow clarity.
- **Rejected alternatives:** (1) Strict state machine -- too complex for
  single-admin manual workflow. (2) JSON assessment -- harder to query and
  validate. (3) Notes as a column on submissions -- can't have multiple
  timestamped entries.
- **Least confident:** Whether 15 agents is the right split or if some agents
  (notes_routes, status_routes) are too thin. The plan phase should merge
  thin agents if they'd only produce <50 lines each.

## Refinement Findings (from brainstorm-refinement agent)

STATUS: PASS -- 5 gaps to address in plan:

1. **CSRF token syntax** must be explicit Coordinated Behaviors entry:
   `{{ csrf_token() }}` with parentheses (CoWorkFlow P1)
2. **Status update route needs BEGIN IMMEDIATE** -- read-then-write on
   terminal state check is a TOCTOU race (RestaurantOps/GymFlow lesson)
3. **isolation_level decision** must be resolved explicitly in plan --
   contradictory guidance across BrewOps (remove it) vs RestaurantOps
   (prescribe it). Resolution: do NOT use isolation_level=None; use default
   autocommit + manual BEGIN IMMEDIATE for transactions.
4. **Fail-closed startup validation** for SECRET_KEY and ADMIN_PASSWORD --
   crash on missing SECRET_KEY, reject weak passwords (Feedback Board lesson)
5. **Negative constraints in Coordinated Behaviors** -- "DO NOT set row_factory
   in model functions", "All timestamps use SQL datetime('now')" (GymFlow lesson)
