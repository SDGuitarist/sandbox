---
title: Gig Outcome Tracker — Implementation Plan
date: 2026-06-05
status: ready
swarm: true
tech_stack: Flask + SQLite + Jinja2
agents: 12
feed_forward:
  risk: "Dashboard aggregation query correctness — no prior solution doc covers paid-only revenue / GROUP BY / COALESCE logic; verified by the deterministic fixture (3 played, $880, 4.5 avg energy, 8000 tips)."
  verify_first: true
---

# Gig Outcome Tracker — Implementation Plan

## 1. Overview

This build adds a brand-new Flask + SQLite + Jinja2 web application under a fresh
`app/` package. It is a single-user gig intelligence tracker: a musician logs
venues, gigs, post-gig outcomes (1:1 per gig), contacts met, debriefs (1:1 per
gig, keyword-searchable), and views aggregate revenue/energy metrics on a
dashboard. The application is built with the Flask app-factory pattern, one model
module and one route blueprint per domain entity, server-rendered Jinja2
templates, and SQLite for storage. There is no existing code to modify — every
file listed in this plan is newly created by exactly one agent.

What must NOT change / must NOT be added (negative scope, enforced):
- **Single-user only.** Auth provides session security only. There are **no
  `user_id` columns** on any domain table and **no ownership checks** in any
  route. Do not add them.
- **No FTS5.** Debrief search is case-insensitive `LIKE` only.
- **No AI parsing.** Debriefs store raw text plus two optional text fields; no
  NLP, no transcription, no structured extraction.
- **No soft deletes.** Deletes are physical, governed by SQLite FK
  `ON DELETE RESTRICT` / `ON DELETE SET NULL` plus route-level status checks.
- **No mesh integration, no export/API, no set-list songs, no voice capture.**
  These are explicitly out of scope.

Meta-goal: this is the **first real swarm build validating the 3-stage
context-death delegation architecture** (no-read discipline, deepen-merge-runner,
swarm-runner). The app is genuinely useful, but the primary objective is proving
12 isolated agents can implement against a shared spec with zero merge conflicts
and zero cross-section contradictions, completing fully unattended
(`final_status: DONE`, `manual_resume: false`).

## 2. Tech Stack & Project Layout

- **Framework:** Flask (app-factory pattern, `create_app()`).
- **DB:** SQLite via the stdlib `sqlite3` module. One connection per request via
  `get_db()`. DB path read from `os.environ['DATABASE']` and stored in
  `app.config['DATABASE']`.
- **Templates:** Jinja2 server-side rendering, single `base.html` layout.
- **CSRF:** Flask-WTF `CSRFProtect` (the only Flask-WTF feature used; forms are
  plain HTML, not WTForms classes).
- **Auth:** username + password, `werkzeug.security` for hashing
  (`generate_password_hash` / `check_password_hash`), Flask `session` for login
  state.

### Directory tree (every path relative to project root)

```
run.py                          # entrypoint: from app import create_app; app = create_app()
schema.sql                      # OPTIONAL aggregate reference only; authoritative DDL lives per model agent
app/
  __init__.py                   # create_app factory, get_db, login_required, init_db, auth blueprint, users DDL
  venue_models.py               # venues table DDL + venue CRUD + venue analytics
  venue_routes.py               # venues blueprint
  gig_models.py                 # gigs table DDL + gig CRUD + status + revenue/analytics
  gig_routes.py                 # gigs blueprint
  outcome_models.py             # outcomes table DDL + outcome CRUD + energy analytics
  outcome_routes.py             # outcomes blueprint
  contact_models.py             # contacts table DDL + contact CRUD + follow-up queries
  contact_routes.py             # contacts blueprint
  debrief_models.py             # debriefs table DDL + debrief CRUD + keyword search
  debrief_routes.py             # debriefs blueprint
  dashboard_routes.py           # dashboard blueprint (aggregation queries live here or call gig/outcome models)
  static/
    style.css
  templates/
    base.html
    auth/
      login.html
      register.html
    venues/
      list.html
      detail.html
      form.html
    gigs/
      list.html
      detail.html
      form.html
    outcomes/
      form.html
      detail.html
    contacts/
      list.html
      follow_ups.html
      detail.html
      form.html
    debriefs/
      form.html
      detail.html
      search.html
    dashboard/
      index.html
```

**Schema initialization:** Each model agent owns its table's `CREATE TABLE
IF NOT EXISTS` DDL as a module-level constant (e.g. `VENUE_SCHEMA`) and a module
function `init_<entity>_schema(conn)`. The scaffold's `init_db()` in
`app/__init__.py` calls each model module's `init_<entity>_schema(conn)` in
dependency order (users → venues → gigs → outcomes/contacts/debriefs) inside one
`with conn:` block. All DDL is idempotent (`IF NOT EXISTS`). The scaffold owns
the `users` table DDL directly.

**Entrypoint (`run.py`):**
```python
from app import create_app
app = create_app()
if __name__ == '__main__':
    app.run(debug=True)
```

## 3. Data Model

All IDs are 8-character UUID hex prefixes (`uuid4().hex[:8]`). All timestamps are
`TEXT DEFAULT (datetime('now'))`. Money is always integer cents, `>= 0`. Each
model agent owns its table's `CREATE TABLE IF NOT EXISTS` (idempotent).

```sql
CREATE TABLE IF NOT EXISTS venues (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  location TEXT,
  venue_type TEXT CHECK(venue_type IN ('hotel','restaurant','private','corporate','festival','other')),
  capacity_estimate INTEGER,
  vibe_notes TEXT,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(name COLLATE NOCASE)
);

CREATE TABLE IF NOT EXISTS gigs (
  id TEXT PRIMARY KEY,
  venue_id TEXT NOT NULL REFERENCES venues(id) ON DELETE RESTRICT,
  date TEXT NOT NULL,  -- YYYY-MM-DD
  event_type TEXT CHECK(event_type IN ('wedding','corporate','restaurant','private_party','festival','public','other')),
  client_name TEXT,
  client_email TEXT,
  planned_set_summary TEXT,
  expected_pay_cents INTEGER CHECK(expected_pay_cents IS NULL OR expected_pay_cents >= 0),
  actual_pay_cents INTEGER CHECK(actual_pay_cents IS NULL OR actual_pay_cents >= 0),
  payment_status TEXT CHECK(payment_status IN ('unpaid','pending','paid')),
  status TEXT NOT NULL CHECK(status IN ('upcoming','played','cancelled')) DEFAULT 'upcoming',
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  CHECK(
    (actual_pay_cents IS NULL AND payment_status IS NULL)
    OR (actual_pay_cents IS NOT NULL AND payment_status IS NOT NULL)
  )
);

CREATE TABLE IF NOT EXISTS outcomes (
  id TEXT PRIMARY KEY,
  gig_id TEXT NOT NULL UNIQUE REFERENCES gigs(id) ON DELETE RESTRICT,
  audience_energy INTEGER NOT NULL CHECK(audience_energy BETWEEN 1 AND 5),
  audience_size_estimate INTEGER CHECK(audience_size_estimate IS NULL OR audience_size_estimate >= 0),
  song_highlights TEXT,
  song_struggles TEXT,
  audience_feedback TEXT,
  staff_feedback TEXT,
  personal_reflections TEXT,
  tips_cents INTEGER NOT NULL DEFAULT 0 CHECK(tips_cents >= 0),
  leads_generated INTEGER NOT NULL DEFAULT 0 CHECK(leads_generated >= 0),
  overall_rating INTEGER NOT NULL CHECK(overall_rating BETWEEN 1 AND 5),
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contacts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT,
  organization TEXT,
  phone TEXT,
  email TEXT,
  met_at_gig_id TEXT REFERENCES gigs(id) ON DELETE SET NULL,
  venue_id TEXT REFERENCES venues(id) ON DELETE SET NULL,
  follow_up_needed INTEGER NOT NULL DEFAULT 0,  -- 0=false, 1=true
  follow_up_date TEXT,  -- YYYY-MM-DD, nullable
  follow_up_notes TEXT,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS debriefs (
  id TEXT PRIMARY KEY,
  gig_id TEXT NOT NULL UNIQUE REFERENCES gigs(id) ON DELETE RESTRICT,
  raw_text TEXT NOT NULL,
  key_takeaways TEXT,
  lessons_learned TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
```

The scaffold also owns the `users` table:
```sql
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);
```

### FK Delete Behavior

| Parent | Child | ON DELETE | Rationale |
|--------|-------|-----------|-----------|
| venues | gigs | RESTRICT | Cannot delete a venue with gig history |
| gigs | outcomes | RESTRICT | Cannot delete a gig that has outcome data |
| gigs | debriefs | RESTRICT | Cannot delete a gig that has a debrief |
| gigs | contacts.met_at_gig_id | SET NULL | Deleting a gig orphans the link, not the contact |
| venues | contacts.venue_id | SET NULL | Deleting a venue orphans the link, not the contact |

### Delete Rules

- **Venues:** Only deletable when no gigs reference them (RESTRICT enforces; route
  catches `sqlite3.IntegrityError` → friendly flash).
- **Gigs:** Only deletable when `status = 'upcoming'` AND no outcome AND no debrief
  (RESTRICT enforces the data side; the route MUST also check `status = 'upcoming'`
  before deleting).
- **Contacts:** Always deletable.
- **Outcomes / Debriefs:** Not deletable (edit to correct).

## 4. Mandatory Spec Section 1 — Export Names Table

Every name that crosses an agent boundary. `conn` is a `sqlite3.Connection` with
`row_factory = sqlite3.Row`. Functions returning scalars return native Python
ints/floats, NOT `Row` objects.

### Model functions — venues (Agent 2, `app/venue_models.py`)

| Name | Type | Defined By | Used By |
|------|------|-----------|---------|
| `VENUE_SCHEMA` | str constant (DDL) | venue_models | scaffold init_db |
| `init_venue_schema(conn) -> None` | function | venue_models | scaffold init_db |
| `create_venue(conn, name, location, venue_type, capacity_estimate, vibe_notes, notes) -> str` (returns new id) | function | venue_models | venue_routes |
| `get_venue(conn, venue_id) -> Row\|None` | function | venue_models | venue_routes, gig_routes, contact_routes |
| `list_venues(conn) -> list[Row]` | function | venue_models | venue_routes, gig_routes, contact_routes (venue select) |
| `update_venue(conn, venue_id, name, location, venue_type, capacity_estimate, vibe_notes, notes) -> None` | function | venue_models | venue_routes |
| `delete_venue(conn, venue_id) -> None` (may raise sqlite3.IntegrityError) | function | venue_models | venue_routes |
| `venue_name_exists(conn, name, exclude_id=None) -> bool` | function | venue_models | venue_routes (unique-name check) |

### Model functions — gigs (Agent 4, `app/gig_models.py`)

| Name | Type | Defined By | Used By |
|------|------|-----------|---------|
| `GIG_SCHEMA` | str constant (DDL) | gig_models | scaffold init_db |
| `init_gig_schema(conn) -> None` | function | gig_models | scaffold init_db |
| `create_gig(conn, venue_id, date, event_type, client_name, client_email, planned_set_summary, expected_pay_cents, notes) -> str` | function | gig_models | gig_routes |
| `get_gig(conn, gig_id) -> Row\|None` | function | gig_models | gig_routes, outcome_routes, debrief_routes, contact_routes |
| `list_gigs(conn, status=None) -> list[Row]` (joins venue name as `venue_name`) | function | gig_models | gig_routes, contact_routes |
| `update_gig(conn, gig_id, date, event_type, client_name, client_email, planned_set_summary, expected_pay_cents, actual_pay_cents, payment_status, notes) -> None` | function | gig_models | gig_routes |
| `delete_gig(conn, gig_id) -> None` (may raise sqlite3.IntegrityError) | function | gig_models | gig_routes |
| `set_gig_status(conn, gig_id, new_status) -> None` | function | gig_models | gig_routes |
| `count_gigs_by_venue(conn, venue_id) -> int` | function | gig_models | venue_routes |
| `list_gigs_by_venue(conn, venue_id) -> list[Row]` | function | gig_models | venue_routes |
| `count_played_gigs(conn) -> int` | function | gig_models | dashboard |
| `total_revenue_cents(conn) -> int` | function | gig_models | dashboard |
| `top_venues(conn, limit=5) -> list[Row]` | function | gig_models | dashboard |
| `recent_gigs(conn, limit=10) -> list[Row]` (joins `venue_name`) | function | gig_models | dashboard |
| `monthly_revenue(conn, months=6) -> list[Row]` | function | gig_models | dashboard |

### Model functions — outcomes (Agent 6, `app/outcome_models.py`)

| Name | Type | Defined By | Used By |
|------|------|-----------|---------|
| `OUTCOME_SCHEMA` | str constant (DDL) | outcome_models | scaffold init_db |
| `init_outcome_schema(conn) -> None` | function | outcome_models | scaffold init_db |
| `create_outcome(conn, gig_id, audience_energy, audience_size_estimate, song_highlights, song_struggles, audience_feedback, staff_feedback, personal_reflections, tips_cents, leads_generated, overall_rating) -> str` | function | outcome_models | outcome_routes |
| `get_outcome_by_gig_id(conn, gig_id) -> Row\|None` | function | outcome_models | outcome_routes, gig_routes |
| `update_outcome(conn, gig_id, audience_energy, audience_size_estimate, song_highlights, song_struggles, audience_feedback, staff_feedback, personal_reflections, tips_cents, leads_generated, overall_rating) -> None` | function | outcome_models | outcome_routes |
| `avg_energy_by_venue(conn, venue_id) -> float\|None` | function | outcome_models | venue_routes |
| `avg_audience_energy(conn) -> float\|None` | function | outcome_models | dashboard |
| `total_tips_cents(conn) -> int` | function | outcome_models | dashboard |

### Model functions — contacts (Agent 8, `app/contact_models.py`)

| Name | Type | Defined By | Used By |
|------|------|-----------|---------|
| `CONTACT_SCHEMA` | str constant (DDL) | contact_models | scaffold init_db |
| `init_contact_schema(conn) -> None` | function | contact_models | scaffold init_db |
| `create_contact(conn, name, role, organization, phone, email, met_at_gig_id, venue_id, follow_up_needed, follow_up_date, follow_up_notes, notes) -> str` | function | contact_models | contact_routes |
| `get_contact(conn, contact_id) -> Row\|None` | function | contact_models | contact_routes |
| `list_contacts(conn) -> list[Row]` | function | contact_models | contact_routes |
| `update_contact(conn, contact_id, name, role, organization, phone, email, met_at_gig_id, venue_id, follow_up_needed, follow_up_date, follow_up_notes, notes) -> None` | function | contact_models | contact_routes |
| `delete_contact(conn, contact_id) -> None` | function | contact_models | contact_routes |
| `list_follow_ups(conn) -> list[Row]` (where follow_up_needed=1, ORDER BY follow_up_date) | function | contact_models | contact_routes |
| `list_contacts_by_gig_id(conn, gig_id) -> list[Row]` | function | contact_models | gig_routes |

### Model functions — debriefs (Agent 10, `app/debrief_models.py`)

| Name | Type | Defined By | Used By |
|------|------|-----------|---------|
| `DEBRIEF_SCHEMA` | str constant (DDL) | debrief_models | scaffold init_db |
| `init_debrief_schema(conn) -> None` | function | debrief_models | scaffold init_db |
| `create_debrief(conn, gig_id, raw_text, key_takeaways, lessons_learned) -> str` | function | debrief_models | debrief_routes |
| `get_debrief_by_gig_id(conn, gig_id) -> Row\|None` | function | debrief_models | debrief_routes, gig_routes |
| `update_debrief(conn, gig_id, raw_text, key_takeaways, lessons_learned) -> None` | function | debrief_models | debrief_routes |
| `search_debriefs(conn, query) -> list[Row]` (joins gig date + venue name) | function | debrief_models | debrief_routes |

### Scaffold exports (Agent 1, `app/__init__.py`)

| Name | Type | Defined By | Used By |
|------|------|-----------|---------|
| `create_app() -> Flask` | factory | scaffold | run.py |
| `get_db() -> sqlite3.Connection` | function | scaffold | every route + model call site |
| `login_required(view) -> view` | decorator | scaffold | every non-auth route |
| `init_db(conn) -> None` | function | scaffold | create_app |
| `auth` | Blueprint (url_prefix `/auth`) | scaffold | registered in create_app |

### Blueprint names + url_prefix

| Blueprint var | Name (for url_for) | url_prefix | Defined By |
|---------------|--------------------|-----------|-----------|
| `auth` | `auth` | `/auth` | scaffold (`app/__init__.py`) |
| `venues_bp` | `venues` | `/venues` | venue_routes |
| `gigs_bp` | `gigs` | `/gigs` | gig_routes |
| `outcomes_bp` | `outcomes` | `/outcomes` | outcome_routes |
| `contacts_bp` | `contacts` | `/contacts` | contact_routes |
| `debriefs_bp` | `debriefs` | `/debriefs` | debrief_routes |
| `dashboard_bp` | `dashboard` | `/dashboard` | dashboard_routes |

### url_for endpoint names (function name within blueprint)

| Endpoint (url_for target) | Method(s) | Route path | Blueprint |
|---------------------------|-----------|-----------|-----------|
| `auth.login` | GET, POST | `/auth/login` | auth |
| `auth.register` | GET, POST | `/auth/register` | auth |
| `auth.logout` | POST | `/auth/logout` | auth |
| `venues.list` | GET | `/venues/` | venues |
| `venues.new` | GET, POST | `/venues/new` | venues |
| `venues.detail` | GET | `/venues/<id>` | venues |
| `venues.edit` | GET, POST | `/venues/<id>/edit` | venues |
| `venues.delete` | POST | `/venues/<id>/delete` | venues |
| `gigs.list` | GET | `/gigs/` | gigs |
| `gigs.new` | GET, POST | `/gigs/new` | gigs |
| `gigs.detail` | GET | `/gigs/<id>` | gigs |
| `gigs.edit` | GET, POST | `/gigs/<id>/edit` | gigs |
| `gigs.delete` | POST | `/gigs/<id>/delete` | gigs |
| `gigs.status` | POST | `/gigs/<id>/status` | gigs |
| `outcomes.new` | GET, POST | `/outcomes/<gig_id>/new` | outcomes |
| `outcomes.view` | GET | `/outcomes/<gig_id>` | outcomes |
| `outcomes.edit` | GET, POST | `/outcomes/<gig_id>/edit` | outcomes |
| `contacts.list` | GET | `/contacts/` | contacts |
| `contacts.follow_ups` | GET | `/contacts/follow-ups` | contacts |
| `contacts.new` | GET, POST | `/contacts/new` | contacts |
| `contacts.detail` | GET | `/contacts/<id>` | contacts |
| `contacts.edit` | GET, POST | `/contacts/<id>/edit` | contacts |
| `contacts.delete` | POST | `/contacts/<id>/delete` | contacts |
| `debriefs.new` | GET, POST | `/debriefs/<gig_id>/new` | debriefs |
| `debriefs.view` | GET | `/debriefs/<gig_id>` | debriefs |
| `debriefs.edit` | GET, POST | `/debriefs/<gig_id>/edit` | debriefs |
| `debriefs.search` | GET | `/debriefs/search` | debriefs |
| `dashboard.index` | GET | `/dashboard/` | dashboard |

> **Route ordering — BINDING on Agent 9 (contact_routes) and Agent 11 (debrief_routes):**
> Static literal paths MUST be declared in code before any `<converter>` paths
> within the same blueprint. Failure to do so causes Flask to match `<id>='new'` or
> `<gig_id>='search'`, making create and search routes 404.
>
> - **Agent 9 (contact_routes) MUST declare in this order:**
>   1. `/contacts/follow-ups` (→ `contacts.follow_ups`)
>   2. `/contacts/new` (→ `contacts.new`)
>   3. `/contacts/<id>` (→ `contacts.detail`)
>   Any other ordering will shadow the static routes with the `<id>` converter.
>
> - **Agent 11 (debrief_routes) MUST declare in this order:**
>   1. `/debriefs/search` (→ `debriefs.search`)
>   2. `/debriefs/<gig_id>` (→ `debriefs.view`)
>   Any other ordering will shadow `/debriefs/search` with the `<gig_id>` converter.

### Cross-boundary scalar/Row usage examples (prevents FC2 — Row vs scalar)

```python
count = count_gigs_by_venue(conn, vid)        # int, NOT a Row
avg = avg_energy_by_venue(conn, vid)          # float or None, NOT a Row
total = total_revenue_cents(conn)             # int, NOT a Row
tips = total_tips_cents(conn)                 # int, NOT a Row
energy = avg_audience_energy(conn)            # float or None, NOT a Row
played = count_played_gigs(conn)              # int, NOT a Row
venue = get_venue(conn, vid)                  # Row or None — access venue['name']
gig = get_gig(conn, gid)                      # Row or None — access gig['date']
outcome = get_outcome_by_gig_id(conn, gid)    # Row or None — None means "no outcome yet"
debrief = get_debrief_by_gig_id(conn, gid)    # Row or None — None means "no debrief yet"
contacts = list_contacts_by_gig_id(conn, gid) # list[Row], possibly empty
top = top_venues(conn, 5)                      # list[Row], each Row has ['name'], ['gig_count']
months = monthly_revenue(conn, 6)              # list[Row], each Row has ['month'], ['total_cents']
```

### Exact Signature & Annotation Compliance (MANDATORY — no simplification)

Every agent MUST reproduce the EXACT function signature and return-type
annotation from the Export Names Table above. Concretely:

- A function declared `-> list[Row]` MUST be annotated `-> list[Row]`, NOT
  `-> list`. Add `from sqlite3 import Row` at the top of each model module so
  the annotation is valid. Do not drop the `[Row]` type parameter.
- A function declared `-> Row | None` MUST be annotated `-> Row | None`
  (or `Optional[Row]`), NOT bare `-> Row` or no annotation.
- A function declared `-> str` returns the new 8-char id string; `-> int` /
  `-> bool` / `-> float | None` annotations must match exactly.
- **Scalar query functions** (`count_gigs_by_venue`, `count_played_gigs`,
  `total_revenue_cents`, `total_tips_cents`, `avg_audience_energy`,
  `avg_energy_by_venue`, `venue_name_exists`) MUST return the scalar itself,
  e.g. `return cur.fetchone()[0]` (an `int`/`float`/`bool`), NEVER a `Row`.
  Wrap nullable averages: `row = cur.fetchone(); return row[0] if row else None`.

These annotations are contract surface — consumers in the Wiring Table rely on
the documented return type (FC1/FC2). Match them character-for-character.

### Negative-Constraint Reaffirmation (each appears exactly as a hard rule)

So there is zero ambiguity, the following prohibitions/requirements are
restated here as a checklist; each is binding on every agent:

- `CSRFProtect(app)` MUST be initialized in `create_app` (scaffold only).
- `row_factory = sqlite3.Row` is set ONLY in `get_db()`; NEVER in a model file.
- Model modules NEVER call `sqlite3.connect(...)` — they receive `conn`.
- `conn.commit()` MUST NOT appear in any model or route file; all writes use
  `with conn:` (the connection's context manager commits/rolls back).
- Python `datetime.now()` MUST NOT appear anywhere; timestamps and
  `updated_at` use SQL `datetime('now')` only.
- Flash categories are EXACTLY `'error'` and `'success'` — no other strings.
- `Markup(...)` is never used in a Jinja2 filter without
  `from markupsafe import escape` applied to every interpolated value first.
- NO `user_id` column on any domain table; NO ownership checks
  (`WHERE user_id = ?`) in any route — single-user app.
- Debrief search binds the SAME `query` string to all three `?` placeholders
  (raw_text, key_takeaways, lessons_learned); case-insensitive `LIKE`, no FTS5.
- Money columns are integer cents, `>= 0` (paired CHECK on pay + status).

## 5. Mandatory Spec Section 2 — Cross-Boundary Wiring Table

Every cross-module call, with import path. Producer defines the function; consumer
imports it.

| Consumer | Producer | Function Signature | Import Path | Purpose |
|----------|----------|--------------------|-------------|---------|
| gig_routes | venue_models | `get_venue(conn, venue_id) -> Row\|None` | `from app.venue_models import get_venue` | Venue name on gig detail; venue list on gig form |
| gig_routes | venue_models | `list_venues(conn) -> list[Row]` | `from app.venue_models import list_venues` | Venue dropdown on gig form |
| gig_routes | outcome_models | `get_outcome_by_gig_id(conn, gig_id) -> Row\|None` | `from app.outcome_models import get_outcome_by_gig_id` | Outcome link/summary on gig detail |
| gig_routes | debrief_models | `get_debrief_by_gig_id(conn, gig_id) -> Row\|None` | `from app.debrief_models import get_debrief_by_gig_id` | Debrief link on gig detail |
| gig_routes | contact_models | `list_contacts_by_gig_id(conn, gig_id) -> list[Row]` | `from app.contact_models import list_contacts_by_gig_id` | Contacts met at this gig |
| gig_routes | gig_models | `create_gig(conn, venue_id, date, event_type, client_name, client_email, planned_set_summary, expected_pay_cents, notes) -> str` | `from app.gig_models import create_gig` | Create gig on new form POST |
| gig_routes | gig_models | `update_gig(conn, gig_id, date, event_type, client_name, client_email, planned_set_summary, expected_pay_cents, actual_pay_cents, payment_status, notes) -> None` | `from app.gig_models import update_gig` | Update gig on edit form POST |
| gig_routes | gig_models | `delete_gig(conn, gig_id) -> None` | `from app.gig_models import delete_gig` | Delete gig on delete POST |
| gig_routes | gig_models | `set_gig_status(conn, gig_id, new_status) -> None` | `from app.gig_models import set_gig_status` | Status transition on status POST |
| gig_routes | gig_models | `list_gigs(conn, status=None) -> list[Row]` | `from app.gig_models import list_gigs` | Gig list page (optional status filter) |
| gig_routes | gig_models | `get_gig(conn, gig_id) -> Row\|None` | `from app.gig_models import get_gig` | Gig detail/edit/delete lookup; delete + status guards |
| venue_routes | gig_models | `count_gigs_by_venue(conn, venue_id) -> int` | `from app.gig_models import count_gigs_by_venue` | Gig count on venue detail |
| venue_routes | gig_models | `list_gigs_by_venue(conn, venue_id) -> list[Row]` | `from app.gig_models import list_gigs_by_venue` | Gig history on venue detail |
| venue_routes | outcome_models | `avg_energy_by_venue(conn, venue_id) -> float\|None` | `from app.outcome_models import avg_energy_by_venue` | Avg audience energy on venue detail |
| venue_routes | venue_models | `get_venue(conn, venue_id) -> Row\|None` | `from app.venue_models import get_venue` | Venue detail/edit lookup |
| venue_routes | venue_models | `list_venues(conn) -> list[Row]` | `from app.venue_models import list_venues` | Venue list page |
| venue_routes | venue_models | `create_venue(conn, name, location, venue_type, capacity_estimate, vibe_notes, notes) -> str` | `from app.venue_models import create_venue` | Create venue on new form POST |
| venue_routes | venue_models | `update_venue(conn, venue_id, name, location, venue_type, capacity_estimate, vibe_notes, notes) -> None` | `from app.venue_models import update_venue` | Update venue on edit form POST |
| venue_routes | venue_models | `delete_venue(conn, venue_id) -> None` | `from app.venue_models import delete_venue` | Delete venue on delete POST |
| venue_routes | venue_models | `venue_name_exists(conn, name, exclude_id=None) -> bool` | `from app.venue_models import venue_name_exists` | Unique-name check on create/edit |
| outcome_routes | gig_models | `get_gig(conn, gig_id) -> Row\|None` | `from app.gig_models import get_gig` | Validate gig exists before outcome create |
| outcome_routes | outcome_models | `create_outcome(conn, gig_id, audience_energy, audience_size_estimate, song_highlights, song_struggles, audience_feedback, staff_feedback, personal_reflections, tips_cents, leads_generated, overall_rating) -> str` | `from app.outcome_models import create_outcome` | Create outcome on new form POST |
| outcome_routes | outcome_models | `update_outcome(conn, gig_id, audience_energy, audience_size_estimate, song_highlights, song_struggles, audience_feedback, staff_feedback, personal_reflections, tips_cents, leads_generated, overall_rating) -> None` | `from app.outcome_models import update_outcome` | Update outcome on edit form POST |
| outcome_routes | outcome_models | `get_outcome_by_gig_id(conn, gig_id) -> Row\|None` | `from app.outcome_models import get_outcome_by_gig_id` | View/edit lookup + duplicate-outcome guard on POST /outcomes/<gig_id>/new |
| debrief_routes | gig_models | `get_gig(conn, gig_id) -> Row\|None` | `from app.gig_models import get_gig` | Validate gig exists before debrief create |
| debrief_routes | debrief_models | `get_debrief_by_gig_id(conn, gig_id) -> Row\|None` | `from app.debrief_models import get_debrief_by_gig_id` | View/edit lookup + duplicate-debrief guard on POST /debriefs/<gig_id>/new |
| contact_routes | gig_models | `get_gig(conn, gig_id) -> Row\|None` | `from app.gig_models import get_gig` | Gig name on contact detail; validate met_at_gig_id |
| contact_routes | venue_models | `get_venue(conn, venue_id) -> Row\|None` | `from app.venue_models import get_venue` | Venue name on contact detail |
| contact_routes | gig_models | `list_gigs(conn) -> list[Row]` | `from app.gig_models import list_gigs` | Gig dropdown on contact form (optional met_at_gig_id) |
| contact_routes | venue_models | `list_venues(conn) -> list[Row]` | `from app.venue_models import list_venues` | Venue dropdown on contact form |
| contact_routes | contact_models | `create_contact(conn, name, role, organization, phone, email, met_at_gig_id, venue_id, follow_up_needed, follow_up_date, follow_up_notes, notes) -> str` | `from app.contact_models import create_contact` | Create contact on new form POST |
| contact_routes | contact_models | `get_contact(conn, contact_id) -> Row\|None` | `from app.contact_models import get_contact` | Contact detail/edit lookup |
| contact_routes | contact_models | `list_contacts(conn) -> list[Row]` | `from app.contact_models import list_contacts` | Contact list page |
| contact_routes | contact_models | `update_contact(conn, contact_id, name, role, organization, phone, email, met_at_gig_id, venue_id, follow_up_needed, follow_up_date, follow_up_notes, notes) -> None` | `from app.contact_models import update_contact` | Update contact on edit form POST |
| contact_routes | contact_models | `delete_contact(conn, contact_id) -> None` | `from app.contact_models import delete_contact` | Delete contact on delete POST |
| contact_routes | contact_models | `list_follow_ups(conn) -> list[Row]` | `from app.contact_models import list_follow_ups` | Follow-ups page |
| dashboard_routes | gig_models | `count_played_gigs(conn) -> int` | `from app.gig_models import count_played_gigs` | Total gigs played |
| dashboard_routes | gig_models | `total_revenue_cents(conn) -> int` | `from app.gig_models import total_revenue_cents` | Total revenue |
| dashboard_routes | gig_models | `top_venues(conn, limit=5) -> list[Row]` | `from app.gig_models import top_venues` | Most-played venues |
| dashboard_routes | gig_models | `recent_gigs(conn, limit=10) -> list[Row]` | `from app.gig_models import recent_gigs` | Recent gigs with venue name |
| dashboard_routes | gig_models | `monthly_revenue(conn, months=6) -> list[Row]` | `from app.gig_models import monthly_revenue` | Monthly revenue trend |
| dashboard_routes | outcome_models | `avg_audience_energy(conn) -> float\|None` | `from app.outcome_models import avg_audience_energy` | Overall avg energy |
| dashboard_routes | outcome_models | `total_tips_cents(conn) -> int` | `from app.outcome_models import total_tips_cents` | Total tips |
| debrief_routes | debrief_models | `search_debriefs(conn, query) -> list[Row]` | `from app.debrief_models import search_debriefs` | Keyword search across debriefs |
| debrief_routes | debrief_models | `create_debrief(conn, gig_id, raw_text, key_takeaways, lessons_learned) -> str` | `from app.debrief_models import create_debrief` | Create debrief on new form POST |
| debrief_routes | debrief_models | `update_debrief(conn, gig_id, raw_text, key_takeaways, lessons_learned) -> None` | `from app.debrief_models import update_debrief` | Update debrief on edit form POST |
| (all routes) | app (scaffold) | `get_db()`, `login_required` | `from app import get_db, login_required` | Request connection + auth gate |

## 6. Mandatory Spec Section 3 — Input Validation Prescriptions

Every POST/PUT route's input rules. **Date guard:** every date-accepting route
uses `re.match(r'^\d{4}-\d{2}-\d{2}$', value)` (Refinement Finding #4). `import re`
at the top of each consuming route module.

| Route | Input | Validation | Error Response |
|-------|-------|------------|----------------|
| POST /auth/register | username | Required, non-empty (after strip) | Flash "Username is required", re-render register |
| POST /auth/register | password | Required, min 8 characters | Flash "Password must be at least 8 characters", re-render |
| POST /auth/register | username | Must not already exist | Flash "Username already taken", re-render |
| POST /auth/login | username/password | Must match a user (check_password_hash) | Flash "Invalid username or password", re-render login |
| POST /venues/new | name | Required, non-empty (after strip) | Flash "Venue name is required", re-render form |
| POST /venues/new | name | Unique case-insensitive (`venue_name_exists`) | Flash "Venue already exists", re-render form |
| POST /venues/new | venue_type | If provided, in allowed set | Flash "Invalid venue type", re-render form |
| POST /venues/new | capacity_estimate | If provided, integer >= 0 | Flash "Capacity must be a non-negative number", re-render |
| POST /venues/<id>/edit | name | Required + unique (`venue_name_exists(exclude_id=id)`) | Flash "Venue name is required" / "Venue already exists" |
| POST /venues/<id>/delete | — | Must have zero gigs (catch sqlite3.IntegrityError) | Flash "Cannot delete venue with gig history", redirect to detail |
| POST /gigs/new | date | **Required, `re.match(r'^\d{4}-\d{2}-\d{2}$', date)`** | Flash "Valid date required (YYYY-MM-DD)", re-render form |
| POST /gigs/new | venue_id | Required, must exist (`get_venue` not None) | Flash "Venue not found", re-render form |
| POST /gigs/new | event_type | If provided, in allowed set | Flash "Invalid event type", re-render form |
| POST /gigs/new | expected_pay_cents | If provided, integer >= 0 | Flash "Pay cannot be negative", re-render |
| POST /gigs/new | payment_status / actual_pay_cents | Not accepted on create — ignore silently (gig starts with NULL payment) | (no error) |
| POST /gigs/<id>/edit | date | **Required, `re.match(r'^\d{4}-\d{2}-\d{2}$', date)`** | Flash "Valid date required (YYYY-MM-DD)", re-render |
| POST /gigs/<id>/edit | actual_pay_cents | If provided, integer >= 0 | Flash "Pay cannot be negative", re-render |
| POST /gigs/<id>/edit | payment_status | If provided, in {unpaid, pending, paid} | Flash "Invalid payment status", re-render |
| POST /gigs/<id>/edit | actual_pay_cents + payment_status | Both set or both empty (paired). If one set, the other required. | Flash "Pay amount and status must be set together", re-render |
| POST /gigs/<id>/status | new_status | Valid transition only: upcoming→played, upcoming→cancelled | Flash "Invalid status transition", redirect to detail |
| POST /gigs/<id>/delete | — | Route MUST verify `status == 'upcoming'` AND `get_outcome_by_gig_id(conn, id) is None` AND `get_debrief_by_gig_id(conn, id) is None` BEFORE calling `delete_gig`; the `sqlite3.IntegrityError` from FK RESTRICT is only the backstop. | Flash "Can only delete upcoming gigs with no outcome or debrief", redirect to detail |
| POST /outcomes/<gig_id>/new | gig_id | Must exist (`get_gig` not None) | Flash "Gig not found", redirect to gigs.list |
| POST /outcomes/<gig_id>/new | gig_id | Must not already have outcome (`get_outcome_by_gig_id` is None) | Flash "Outcome already exists for this gig", redirect to outcomes.view |
| POST /outcomes/<gig_id>/new | audience_energy | Required, integer 1-5 | Flash "Energy must be 1-5", re-render form |
| POST /outcomes/<gig_id>/new | overall_rating | Required, integer 1-5 | Flash "Rating must be 1-5", re-render form |
| POST /outcomes/<gig_id>/new | tips_cents | If provided, integer >= 0 (default 0) | Flash "Tips cannot be negative", re-render |
| POST /outcomes/<gig_id>/new | leads_generated | If provided, integer >= 0 (default 0) | Flash "Leads cannot be negative", re-render |
| POST /outcomes/<gig_id>/edit | audience_energy / overall_rating | Same 1-5 rules as create | Same flashes |
| POST /outcomes/<gig_id>/edit | tips_cents | If provided, integer >= 0 (default 0) | Flash "Tips cannot be negative", re-render |
| POST /outcomes/<gig_id>/edit | leads_generated | If provided, integer >= 0 (default 0) | Flash "Leads cannot be negative", re-render |
| POST /contacts/new | name | Required, non-empty (after strip) | Flash "Contact name is required", re-render |
| POST /contacts/new | met_at_gig_id | If provided, must exist (`get_gig` not None) | Flash "Gig not found", re-render |
| POST /contacts/new | venue_id | If provided, must exist (`get_venue` not None) | Flash "Venue not found", re-render |
| POST /contacts/new | follow_up_date | **If provided, `re.match(r'^\d{4}-\d{2}-\d{2}$', follow_up_date)`** | Flash "Valid date required for follow-up", re-render |
| POST /contacts/<id>/edit | name | Required, non-empty | Flash "Contact name is required", re-render |
| POST /contacts/<id>/edit | follow_up_date | **If provided, `re.match(r'^\d{4}-\d{2}-\d{2}$', follow_up_date)`** | Flash "Valid date required for follow-up", re-render |
| POST /debriefs/<gig_id>/new | gig_id | Must exist (`get_gig` not None) | Flash "Gig not found", redirect to gigs.list |
| POST /debriefs/<gig_id>/new | gig_id | Must not already have debrief (`get_debrief_by_gig_id` is None) | Flash "Debrief already exists for this gig", redirect to debriefs.view |
| POST /debriefs/<gig_id>/new | raw_text | Required, non-empty (after strip) | Flash "Debrief text is required", re-render form |
| POST /debriefs/<gig_id>/edit | raw_text | Required, non-empty | Flash "Debrief text is required", re-render form |

**Integer parsing convention:** all integer inputs (`*_cents`, `capacity_estimate`,
`audience_energy`, `overall_rating`, `leads_generated`, `audience_size_estimate`)
are parsed with a helper pattern: empty string → None (or default where the column
is NOT NULL DEFAULT), non-empty → `int(value)` inside a `try/except ValueError`
that flashes the field's negative/format error. Booleans (`follow_up_needed`) are
`1 if request.form.get('follow_up_needed') else 0`.

## 7. Mandatory Spec Section 4 — Coordinated Behaviors

Each rule is concrete and binding on every agent that touches the relevant surface.

1. **CSRF tokens.** Flask-WTF `CSRFProtect(app)` is initialized in `create_app`.
   EVERY POST form in EVERY template includes `{{ csrf_token() }}` **with
   parentheses** as a hidden input:
   `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`. (FC1
   variant.) No POST form may omit it.

2. **SECRET_KEY — fail closed.** In `create_app`:
   `app.config['SECRET_KEY'] = os.environ['SECRET_KEY']`. If the env var is
   missing, `raise RuntimeError("SECRET_KEY environment variable is required")`.
   **No dev fallback, no `or 'dev'`.** (FC10.)

3. **SESSION_COOKIE_SECURE — env-gated.**
   `app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'`.
   NOT unconditional `True` (would break local HTTP dev sessions and smoke tests).
   (Refinement Finding #1.)

4. **DATABASE config.** `create_app` maps
   `app.config['DATABASE'] = os.environ['DATABASE']` (fail closed if missing).
   Smoke tests set `DATABASE` to a **tempfile path** (e.g. via
   `tempfile.mkstemp`), **never `:memory:`** (a `:memory:` DB is not shared across
   connections). (FC49.)

5. **get_db() — one canonical helper.** Defined ONLY in `app/__init__.py`:
   ```python
   def get_db():
       if 'db' not in g:
           g.db = sqlite3.connect(current_app.config['DATABASE'])
           g.db.row_factory = sqlite3.Row
           g.db.execute('PRAGMA foreign_keys = ON')
       return g.db
   ```
   `row_factory = sqlite3.Row` is set **ONLY here**, never inside any model file.
   Every connection sets `PRAGMA foreign_keys = ON`. A `teardown_appcontext` closes
   the connection. (FC40 + negative constraint: **DO NOT set row_factory or open
   connections inside model modules** — models receive `conn` as a parameter.)

   **init_db / PRAGMA foreign_keys — per-connection requirement (FC40 extension).**
   `PRAGMA foreign_keys` is a per-connection setting — it MUST fire on EVERY
   connection path, not only `get_db`. `create_app` MUST obtain the connection it
   passes to `init_db` via a path that also runs `PRAGMA foreign_keys = ON`. Two
   acceptable patterns:
   - **Preferred:** call `init_db(get_db())` inside a pushed app context so the
     same `get_db` helper runs the PRAGMA; OR
   - **Standalone:** if opening a `sqlite3.connect(app.config['DATABASE'])` for
     initialization separately, that connection MUST execute
     `conn.execute('PRAGMA foreign_keys = ON')` before any DDL and then be closed.

   If `init_db` runs with FK enforcement OFF, all `ON DELETE RESTRICT` / `ON DELETE
   SET NULL` behaviors the spec depends on are silently unenforced during seeding and
   migration — this is the highest-severity silent failure class (FC40).

6. **Timestamps.** SQL `datetime('now')` ONLY (column defaults + `updated_at`
   reassignment in UPDATE statements via `updated_at = datetime('now')`). **NEVER**
   Python `datetime.now()` anywhere.

7. **login_required.** Decorator defined in `app/__init__.py`. Applied to EVERY
   non-auth route (all of venues, gigs, outcomes, contacts, debriefs, dashboard,
   plus `auth.logout`). Unauthenticated request → `redirect(url_for('auth.login'))`.
   Checks `session.get('user_id')`.

8. **Flash message categories.** Exactly two categories: `flash(msg, 'error')` and
   `flash(msg, 'success')`. All 12 agents use these two strings only. `base.html`
   renders flashed messages with `get_flashed_messages(with_categories=true)` and
   styles by category.

9. **Navbar.** `base.html` renders, in order:
   **Dashboard** (`url_for('dashboard.index')`) | **Gigs** (`url_for('gigs.list')`)
   | **Venues** (`url_for('venues.list')`) | **Contacts** (`url_for('contacts.list')`)
   | **Logout**. Logout is a POST form to `url_for('auth.logout')` containing the
   CSRF hidden input. The navbar is shown only when logged in
   (`{% if session.get('user_id') %}`).

10. **Jinja2 custom filters.** If ANY agent writes a custom Jinja filter that
    returns `Markup(...)` (e.g. a status badge, rating stars, or debrief excerpt),
    it MUST `from markupsafe import escape` and escape every interpolated value
    before wrapping: `Markup(f'<span>{escape(value)}</span>')`. **Negative
    constraint: DO NOT use `Markup()` in a filter without escaping interpolated
    inputs first.** (FC47, Refinement Finding #3.) Default expectation: agents
    rely on Jinja autoescaping and avoid custom `Markup` filters unless necessary.

11. **Blueprint registration & prefixes.** ALL blueprints are registered in
    `create_app`. Each blueprint is created with its `url_prefix` (`/venues`,
    `/gigs`, `/outcomes`, `/contacts`, `/debriefs`, `/dashboard`, `/auth`). Route
    decorators inside each module are **RELATIVE to the prefix** — e.g. venues uses
    `@venues_bp.route('/')` for `/venues/`, `@venues_bp.route('/new')` for
    `/venues/new`, `@venues_bp.route('/<id>')` for `/venues/<id>`. **NO prefix
    doubling** — never write `@venues_bp.route('/venues/new')`. (FC7.)

12. **ID generation.** New IDs are `uuid4().hex[:8]` generated **inside the model
    `create_*` function** (not the route). `import uuid` in each model module.

## 8. Mandatory Spec Section 5 — Transaction Contracts

Every model write function. **Pattern rule:** ALL transactional writes use
`with conn:` — the only reliable atomic pattern in Python 3.14+ (Refinement Finding
#2). **NO bare `conn.execute('BEGIN')` + `conn.commit()`. NO scattered
`conn.commit()` mid-function.** Reads do not need `with conn:`.

| Function | Writes | Pattern | Error Handling |
|----------|--------|---------|----------------|
| `create_venue` | INSERT venues | single stmt in `with conn:` (commits internally) | route catches `sqlite3.IntegrityError` (UNIQUE name) → flash "Venue already exists" |
| `update_venue` | UPDATE venues (set `updated_at=datetime('now')`) | single stmt in `with conn:` | route catches `sqlite3.IntegrityError` → flash "Venue already exists" |
| `delete_venue` | DELETE venues | single stmt in `with conn:` | route catches `sqlite3.IntegrityError` (FK RESTRICT, gigs exist) → flash "Cannot delete venue with gig history" |
| `create_gig` | INSERT gigs | single stmt in `with conn:` | route catches `sqlite3.IntegrityError` (FK venue missing / CHECK) → flash validation error |
| `update_gig` | UPDATE gigs (`updated_at=datetime('now')`) | single stmt in `with conn:` | route catches `sqlite3.IntegrityError` (paired-pay CHECK) → flash "Pay amount and status must be set together" |
| `set_gig_status` | UPDATE gigs status (`updated_at=datetime('now')`) | single stmt in `with conn:` | route validates transition BEFORE call and flashes "Invalid status transition" itself — the `gigs.status` CHECK only constrains the value set {upcoming,played,cancelled}, NOT the transition direction; an invalid transition (e.g. played→upcoming) passes the CHECK and raises NO IntegrityError, so the transition guard is purely route-level. Do NOT rely on IntegrityError here. |
| `delete_gig` | DELETE gigs | single stmt in `with conn:` (route pre-checks status=='upcoming') | route catches `sqlite3.IntegrityError` (RESTRICT outcome/debrief) → flash "Can only delete upcoming gigs with no outcome or debrief" |
| `create_outcome` | INSERT outcomes | single stmt in `with conn:` | route catches `sqlite3.IntegrityError` (UNIQUE gig_id) → flash "Outcome already exists for this gig" |
| `update_outcome` | UPDATE outcomes (`updated_at=datetime('now')`) | single stmt in `with conn:` | route catches `sqlite3.IntegrityError` (CHECK energy/rating) → flash range error |
| `create_contact` | INSERT contacts | single stmt in `with conn:` | route catches `sqlite3.IntegrityError` (FK) → flash "Gig not found"/"Venue not found" |
| `update_contact` | UPDATE contacts (`updated_at=datetime('now')`) | single stmt in `with conn:` | route catches `sqlite3.IntegrityError` (FK) → flash |
| `delete_contact` | DELETE contacts | single stmt in `with conn:` | always allowed; no special handling |
| `create_debrief` | INSERT debriefs | single stmt in `with conn:` | route catches `sqlite3.IntegrityError` (UNIQUE gig_id) → flash "Debrief already exists for this gig" |
| `update_debrief` | UPDATE debriefs (`updated_at=datetime('now')`) | single stmt in `with conn:` | route catches `sqlite3.IntegrityError` → flash |
| `init_<entity>_schema` | CREATE TABLE IF NOT EXISTS | called inside scaffold's single `with conn:` in `init_db` | idempotent; no special handling |

**Negative constraint:** catch `sqlite3.IntegrityError` **specifically**, never a
bare `except:` or `except Exception:`. Validation that can be checked in Python
(required fields, ranges, date format, paired-pay) is checked in the route BEFORE
the model call; the IntegrityError catch is a backstop for DB-enforced constraints
(UNIQUE, FK RESTRICT, CHECK).

## 9. Mandatory Spec Section 6 — Authorization Matrix

All routes require login EXCEPT `auth.login` and `auth.register`. This is a
**single-user app: there are no `user_id` columns and NO ownership checks**. Agents
MUST NOT add any per-record ownership filtering or `WHERE user_id = ?` clauses —
there is exactly one user; the `login_required` session gate is the entire
authorization model.

| Route Group | Mode | Notes |
|-------------|------|-------|
| GET/POST /auth/login | public | Unauthenticated access |
| GET/POST /auth/register | public | Unauthenticated access |
| POST /auth/logout | role-only (login required) | Session teardown |
| /venues/* | role-only (login required) | All CRUD + delete |
| /gigs/* | role-only (login required) | All CRUD + status + delete |
| /outcomes/* | role-only (login required) | Create, view, edit |
| /contacts/* | role-only (login required) | All CRUD + follow-ups + delete |
| /debriefs/* | role-only (login required) | Create, view, edit, search |
| /dashboard/ | role-only (login required) | Read-only |

"role-only" here means: authenticated session present. There is one role
(the single user). Unauthenticated requests to protected routes redirect to
`auth.login`.

## 10. Routes

| Method | Path | Action | Agent |
|--------|------|--------|-------|
| GET | /auth/login | Login form | scaffold |
| POST | /auth/login | Authenticate | scaffold |
| GET | /auth/register | Register form | scaffold |
| POST | /auth/register | Create account | scaffold |
| POST | /auth/logout | Logout | scaffold |
| GET | /venues/ | List all venues | venue_routes |
| GET | /venues/new | Create venue form | venue_routes |
| POST | /venues/new | Create venue | venue_routes |
| GET | /venues/\<id\> | Venue detail (gig history, avg energy) | venue_routes |
| GET | /venues/\<id\>/edit | Edit venue form | venue_routes |
| POST | /venues/\<id\>/edit | Update venue | venue_routes |
| POST | /venues/\<id\>/delete | Delete venue (RESTRICT) | venue_routes |
| GET | /gigs/ | List all gigs | gig_routes |
| GET | /gigs/new | Create gig form | gig_routes |
| POST | /gigs/new | Create gig | gig_routes |
| GET | /gigs/\<id\> | Gig detail (hub page) | gig_routes |
| GET | /gigs/\<id\>/edit | Edit gig form | gig_routes |
| POST | /gigs/\<id\>/edit | Update gig | gig_routes |
| POST | /gigs/\<id\>/delete | Delete gig (upcoming only) | gig_routes |
| POST | /gigs/\<id\>/status | Change status | gig_routes |
| GET | /outcomes/\<gig_id\>/new | Outcome form (create) | outcome_routes |
| POST | /outcomes/\<gig_id\>/new | Create outcome | outcome_routes |
| GET | /outcomes/\<gig_id\> | View outcome | outcome_routes |
| GET | /outcomes/\<gig_id\>/edit | Edit outcome form | outcome_routes |
| POST | /outcomes/\<gig_id\>/edit | Update outcome | outcome_routes |
| GET | /contacts/ | List all contacts | contact_routes |
| GET | /contacts/follow-ups | Follow-up list | contact_routes |
| GET | /contacts/new | Create contact form | contact_routes |
| POST | /contacts/new | Create contact | contact_routes |
| GET | /contacts/\<id\> | Contact detail | contact_routes |
| GET | /contacts/\<id\>/edit | Edit contact form | contact_routes |
| POST | /contacts/\<id\>/edit | Update contact | contact_routes |
| POST | /contacts/\<id\>/delete | Delete contact | contact_routes |
| GET | /debriefs/\<gig_id\>/new | Debrief form (create) | debrief_routes |
| POST | /debriefs/\<gig_id\>/new | Create debrief | debrief_routes |
| GET | /debriefs/\<gig_id\> | View debrief | debrief_routes |
| GET | /debriefs/\<gig_id\>/edit | Edit debrief form | debrief_routes |
| POST | /debriefs/\<gig_id\>/edit | Update debrief | debrief_routes |
| GET | /debriefs/search | Search debriefs | debrief_routes |
| GET | /dashboard/ | Dashboard overview | dashboard |

## 11. Templates

```
templates/
  base.html              (scaffold — navbar, flash messages, auth links)
  auth/
    login.html            (scaffold)
    register.html         (scaffold)
  venues/
    list.html             (venue_routes)
    detail.html           (venue_routes — gig history + avg energy)
    form.html             (venue_routes — create and edit, shared template)
  gigs/
    list.html             (gig_routes — filterable by status)
    detail.html           (gig_routes — hub: links to outcome, debrief, venue, contacts)
    form.html             (gig_routes — create and edit, shared template)
  outcomes/
    form.html             (outcome_routes — create and edit, shared template)
    detail.html           (outcome_routes — read-only view)
  contacts/
    list.html             (contact_routes — all contacts)
    follow_ups.html       (contact_routes — follow-up list, filtered)
    detail.html           (contact_routes)
    form.html             (contact_routes — create and edit, shared template)
  debriefs/
    form.html             (debrief_routes — create and edit, shared template)
    detail.html           (debrief_routes — read-only view)
    search.html           (debrief_routes — search results)
  dashboard/
    index.html            (dashboard — all dashboard widgets)
```

Every template `{% extends "base.html" %}`. Every POST form includes the CSRF
hidden input. The gig detail hub shows: gig info + edit/delete buttons (delete only
when `gig.status == 'upcoming'` and no outcome and no debrief), status-transition
buttons (upcoming→played, upcoming→cancelled), "Add Outcome" or view/edit link,
"Add Debrief" or view/edit link, contacts-met list + "Add Contact" link, and a link
to the venue detail.

## 12. Dashboard Calculations

These exact queries are load-bearing (the Feed-Forward risk). Each lives in the
producer model function named in Section 4.

```sql
-- count_played_gigs
SELECT COUNT(*) FROM gigs WHERE status = 'played';

-- total_revenue_cents (pay + tips, played gigs with payment_status = 'paid' only)
SELECT COALESCE(SUM(g.actual_pay_cents), 0) + COALESCE(SUM(o.tips_cents), 0)
FROM gigs g
LEFT JOIN outcomes o ON o.gig_id = g.id
WHERE g.status = 'played' AND g.payment_status = 'paid';

-- avg_audience_energy (all outcomes)
SELECT AVG(audience_energy) FROM outcomes;

-- top_venues (top 5 by played gig count)
SELECT v.name, COUNT(g.id) as gig_count
FROM venues v JOIN gigs g ON g.venue_id = v.id
WHERE g.status = 'played'
GROUP BY v.id ORDER BY gig_count DESC LIMIT 5;

-- recent_gigs (10, any status, newest first)
SELECT g.*, v.name as venue_name
FROM gigs g JOIN venues v ON g.venue_id = v.id
ORDER BY g.date DESC LIMIT 10;

-- monthly_revenue (last 6 months, pay + tips, paid only)
SELECT strftime('%Y-%m', g.date) as month,
       COALESCE(SUM(g.actual_pay_cents), 0) + COALESCE(SUM(o.tips_cents), 0) as total_cents
FROM gigs g
LEFT JOIN outcomes o ON o.gig_id = g.id
WHERE g.status = 'played' AND g.payment_status = 'paid'
  AND g.date >= date('now', '-6 months')
GROUP BY month ORDER BY month;

-- total_tips_cents
SELECT COALESCE(SUM(tips_cents), 0) FROM outcomes;
```

Scalar functions return native ints/floats (`row[0]`), NOT Row objects.
`avg_audience_energy` and `avg_energy_by_venue` return `None` when there are no
outcomes (SQLite `AVG` over zero rows is NULL).

Supporting venue-detail analytic:
```sql
-- avg_energy_by_venue
SELECT AVG(o.audience_energy)
FROM outcomes o JOIN gigs g ON g.id = o.gig_id
WHERE g.venue_id = ?;
```

## 13. Debrief Search Semantics

Case-insensitive `LIKE` against `raw_text`, `key_takeaways`, `lessons_learned`. No
FTS5. The `%` wrapping lives in SQL; the user input is bound via `?` (no wildcard
injection risk).

```sql
-- search_debriefs(conn, query)
SELECT d.*, g.date as gig_date, v.name as venue_name
FROM debriefs d
JOIN gigs g ON g.id = d.gig_id
JOIN venues v ON v.id = g.venue_id
WHERE d.raw_text LIKE '%' || ? || '%'
   OR d.key_takeaways LIKE '%' || ? || '%'
   OR d.lessons_learned LIKE '%' || ? || '%'
ORDER BY g.date DESC;
```

The same `query` string is bound to all three `?` placeholders. An empty/whitespace
query returns an empty result list (route short-circuits before calling, or the
function returns `[]`).

## 14. Acceptance Tests (EARS)

Notation: `WHEN [condition] THE SYSTEM SHALL [behavior]`.

### Happy Path

- WHEN a visitor submits the register form with a new username and an 8+ char
  password THE SYSTEM SHALL create the user and redirect (302) to `/auth/login`.
- WHEN a registered user submits valid credentials to `/auth/login` THE SYSTEM
  SHALL set the session and redirect (302) to `/dashboard/`.
- WHEN an authenticated user POSTs a valid venue to `/venues/new` THE SYSTEM SHALL
  insert the venue and redirect (302) to `/venues/<id>`.
- WHEN an authenticated user GETs `/venues/<id>` THE SYSTEM SHALL return 200 showing
  the venue's gig count and average audience energy.
- WHEN an authenticated user POSTs a valid edit to `/venues/<id>/edit` THE SYSTEM
  SHALL update the venue and redirect (302) to `/venues/<id>`.
- WHEN an authenticated user POSTs a valid gig (valid date, existing venue) to
  `/gigs/new` THE SYSTEM SHALL insert the gig with status `upcoming` and redirect
  (302) to `/gigs/<id>`.
- WHEN an authenticated user GETs `/gigs/<id>` THE SYSTEM SHALL return 200 rendering
  the hub with outcome status, debrief status, contacts list, and venue link.
- WHEN an authenticated user POSTs `new_status=played` to `/gigs/<id>/status` on an
  upcoming gig THE SYSTEM SHALL set status to `played` and redirect (302) to
  `/gigs/<id>`.
- WHEN an authenticated user POSTs a valid outcome (energy 1-5, rating 1-5) to
  `/outcomes/<gig_id>/new` for a gig with no outcome THE SYSTEM SHALL insert the
  outcome and redirect (302) to `/outcomes/<gig_id>`.
- WHEN an authenticated user POSTs a valid edit to `/outcomes/<gig_id>/edit` THE
  SYSTEM SHALL update the outcome and redirect (302) to `/outcomes/<gig_id>`.
- WHEN an authenticated user POSTs a valid contact to `/contacts/new` THE SYSTEM
  SHALL insert the contact and redirect (302) to `/contacts/<id>`.
- WHEN an authenticated user GETs `/contacts/follow-ups` THE SYSTEM SHALL return 200
  listing ONLY contacts where `follow_up_needed = 1`, sorted by `follow_up_date`.
- WHEN an authenticated user POSTs a valid debrief (non-empty raw_text) to
  `/debriefs/<gig_id>/new` for a gig with no debrief THE SYSTEM SHALL insert it and
  redirect (302) to `/debriefs/<gig_id>`.
- WHEN an authenticated user GETs `/debriefs/search?q=<kw>` THE SYSTEM SHALL return
  200 listing debriefs whose raw_text/key_takeaways/lessons_learned contain the
  keyword (case-insensitive).
- WHEN the fixture (Section: Verification Commands) is seeded and an authenticated
  user GETs `/dashboard/` THE SYSTEM SHALL return 200 rendering: 3 played gigs,
  88000-cent ($880) total revenue, 4.5 average audience energy, 8000-cent total
  tips, Grand Ballroom above Sunset Lounge in top venues.
- WHEN an authenticated user POSTs `/gigs/<id>/delete` on an upcoming gig with no
  outcome/debrief THE SYSTEM SHALL delete it and redirect (302) to `/gigs/`.
- WHEN an authenticated user POSTs `/venues/<id>/delete` on a venue with no gigs THE
  SYSTEM SHALL delete it and redirect (302) to `/venues/`.
- WHEN an authenticated user POSTs `/contacts/<id>/delete` on any contact THE SYSTEM
  SHALL delete it and redirect (302) to `/contacts/`.

### Error Cases

- WHEN register is submitted with an existing username THE SYSTEM SHALL re-render
  register with flash "Username already taken" and create no user.
- WHEN register is submitted with a password under 8 chars THE SYSTEM SHALL
  re-render with flash "Password must be at least 8 characters".
- WHEN login is submitted with wrong credentials THE SYSTEM SHALL re-render login
  with flash "Invalid username or password" and set no session.
- WHEN any protected route is requested without a session THE SYSTEM SHALL redirect
  (302) to `/auth/login`.
- WHEN `/venues/new` is POSTed with a name that already exists (case-insensitive)
  THE SYSTEM SHALL re-render with flash "Venue already exists" and insert nothing.
- WHEN `/venues/<id>/delete` is POSTed for a venue that has gigs THE SYSTEM SHALL
  block the delete (FK RESTRICT → caught IntegrityError) and flash "Cannot delete
  venue with gig history".
- WHEN `/gigs/new` is POSTed with a malformed date (fails
  `^\d{4}-\d{2}-\d{2}$`) THE SYSTEM SHALL re-render with flash "Valid date required
  (YYYY-MM-DD)" and insert nothing.
- WHEN `/gigs/<id>/delete` is POSTed for a non-upcoming gig (or one with an
  outcome/debrief) THE SYSTEM SHALL block and flash "Can only delete upcoming gigs
  with no outcome or debrief".
- WHEN `/gigs/<id>/status` is POSTed with an invalid transition (e.g. played→upcoming)
  THE SYSTEM SHALL leave status unchanged and flash "Invalid status transition".
- WHEN `/outcomes/<gig_id>/new` is POSTed for a gig that already has an outcome THE
  SYSTEM SHALL flash "Outcome already exists for this gig" and insert nothing.
- WHEN `/outcomes/<gig_id>/new` is POSTed with `audience_energy` outside 1-5 THE
  SYSTEM SHALL re-render with flash "Energy must be 1-5" and insert nothing.
- WHEN `/gigs/<id>/edit` is POSTed with `actual_pay_cents` set but `payment_status`
  empty (or vice versa) THE SYSTEM SHALL re-render with flash "Pay amount and status
  must be set together" and update nothing (paired CHECK).
- WHEN `/debriefs/<gig_id>/new` is POSTed for a gig that already has a debrief THE
  SYSTEM SHALL flash "Debrief already exists for this gig" and insert nothing.
- WHEN `/contacts/new` is POSTed with a malformed `follow_up_date` THE SYSTEM SHALL
  re-render with flash "Valid date required for follow-up" and insert nothing.

### Verification Commands

Basis: the brief's Smoke Test Routes table (23 routes) and Dashboard Smoke Test
Fixtures. The smoke test runs against a tempfile DB (`DATABASE=<tempfile>`,
`SECRET_KEY=test`, `FLASK_ENV` unset so cookies are not Secure-only), registers +
logs in (persisting the session cookie + CSRF token across requests), then exercises
each route. Status assertions below use `-o /dev/null -w '%{http_code}'` against the
Flask test client or a running dev server; redirects are asserted by `302` and the
`Location` header (do NOT follow with `-L` when asserting the 302).

| EARS criterion | Verify |
|----------------|--------|
| register happy | `POST /auth/register` (valid) → status `302`, Location `/auth/login` |
| login happy | `POST /auth/login` (valid) → status `302`, Location `/dashboard/` |
| venues list auth | `GET /venues/` (logged in) → status `200` |
| venue create | `POST /venues/new` (valid) → status `302`, Location `/venues/<id>` |
| venue detail | `GET /venues/<id>` → status `200` |
| venue edit | `POST /venues/<id>/edit` (valid) → status `302` → `/venues/<id>` |
| gigs list | `GET /gigs/` → status `200` |
| gig create | `POST /gigs/new` (valid) → status `302` → `/gigs/<id>` |
| gig detail hub | `GET /gigs/<id>` → status `200`, body contains venue name + "Add Outcome"/"Add Debrief" |
| gig edit | `POST /gigs/<id>/edit` (valid) → status `302` → `/gigs/<id>` |
| gig status | `POST /gigs/<id>/status` (new_status=played) → status `302` → `/gigs/<id>` |
| outcome create | `POST /outcomes/<gig_id>/new` (valid) → status `302` → `/outcomes/<gig_id>` |
| outcome edit | `POST /outcomes/<gig_id>/edit` (valid) → status `302` → `/outcomes/<gig_id>` |
| contacts list | `GET /contacts/` → status `200` |
| contact create | `POST /contacts/new` (valid) → status `302` → `/contacts/<id>` |
| follow-ups filtered | `GET /contacts/follow-ups` → status `200`, body lists only follow_up_needed=1 |
| debrief create | `POST /debriefs/<gig_id>/new` (valid) → status `302` → `/debriefs/<gig_id>` |
| debrief search | `GET /debriefs/search?q=test` → status `200` |
| dashboard | `GET /dashboard/` → status `200` |
| gig delete | `POST /gigs/<id>/delete` (upcoming, no outcome/debrief) → status `302` → `/gigs/` |
| venue delete | `POST /venues/<id>/delete` (no gigs) → status `302` → `/venues/` |
| contact delete | `POST /contacts/<id>/delete` → status `302` → `/contacts/` |
| dashboard totals (fixture) | Seed the 4-gig fixture via POST routes, then `GET /dashboard/`; assert rendered HTML contains `880` (or `$880.00`), `4.5`, `80.00`/`8000` tips, `3` played, and Grand Ballroom listed above Sunset Lounge |
| venue unique reject | `POST /venues/new` (dup name) → status `200` (re-render), body contains "Venue already exists" |
| venue delete RESTRICT | `POST /venues/<id>/delete` (has gigs) → redirect to detail, flash "Cannot delete venue with gig history" |
| gig delete reject | `POST /gigs/<id>/delete` (played) → redirect to detail, flash "Can only delete upcoming gigs..." |
| outcome dup reject | `POST /outcomes/<gig_id>/new` (already exists) → flash "Outcome already exists for this gig" |
| energy range reject | `POST /outcomes/<gig_id>/new` (energy=9) → status `200`, body "Energy must be 1-5" |
| paired-pay reject | `POST /gigs/<id>/edit` (actual_pay set, status empty) → status `200`, body "Pay amount and status must be set together" |
| date format reject | `POST /gigs/new` (date="06/05/2026") → status `200`, body "Valid date required" |

**Fixture (seed via POST routes, in order):** create venues "The Grand Ballroom"
and "Sunset Lounge"; create Gig 1 (2026-05-01, Grand Ballroom) → status played →
edit actual_pay_cents=50000/payment_status=paid → outcome energy=4 tips=5000
rating=4; Gig 2 (2026-05-15, Sunset Lounge) → played → 30000/paid → outcome energy=5
tips=3000 rating=5; Gig 3 (2026-06-01, Grand Ballroom) → played → 45000/unpaid (no
outcome); Gig 4 (2026-06-10, Sunset Lounge) → upcoming, expected_pay_cents=40000 (no
outcome). Expected dashboard: 3 played, 88000 revenue, 4.5 avg energy, 8000 tips,
top venues Grand Ballroom (2) then Sunset Lounge (1).

## 15. Swarm Agent Assignment

**Total agents:** 12
**Total files:** 33
**Validation:** No file appears in multiple assignments. Every file in the directory tree is owned by exactly one agent. Paths are relative to project root; no absolute paths, no `..`.

### Shared Interface Spec

All agents implement against Sections 4–9 of this plan (Export Names Table,
Cross-Boundary Wiring Table, Input Validation Prescriptions, Coordinated Behaviors,
Transaction Contracts, Authorization Matrix). The key rules every agent must follow:

- Import `get_db` and `login_required` from `app` (`from app import get_db, login_required`).
- Apply `@login_required` to every non-auth route view function.
- Every POST form template must include `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
- Flash categories are exactly `'error'` and `'success'` — no other strings.
- Write transactions use `with conn:` only. No `conn.commit()`, no bare `BEGIN`.
- Catch `sqlite3.IntegrityError` specifically — never bare `except`.
- IDs are `uuid4().hex[:8]`, generated inside the model `create_*` function.
- Timestamps: `datetime('now')` in SQL only. Never Python `datetime.now()`.
- Models receive `conn` as a parameter. Models never open connections or set `row_factory`.
- Route decorators are relative to the blueprint prefix — never doubled.
- Blueprint variable names and `name=` args must match the Export Names Table exactly.

---

### Agent: scaffold
**Blueprint:** `auth` (url_prefix `/auth`)
**Files:**
- `run.py`
- `app/__init__.py`
- `app/static/style.css`
- `app/templates/base.html`
- `app/templates/auth/login.html`
- `app/templates/auth/register.html`

**Responsibility:** Implements `create_app()`, `get_db()`, `login_required`, `init_db()`, the `users` table DDL, and the `auth` blueprint (register/login/logout routes + templates), plus `base.html` with navbar and flash rendering, and global CSS.

---

### Agent: venue_models
**Blueprint:** none
**Files:**
- `app/venue_models.py`

**Responsibility:** Implements the `venues` table DDL (`VENUE_SCHEMA`, `init_venue_schema`), all venue CRUD functions (`create_venue`, `get_venue`, `list_venues`, `update_venue`, `delete_venue`, `venue_name_exists`), and the venue analytics function (`avg_energy_by_venue` is in outcome_models — see Export Names Table; venue_models owns only venue-table operations).

---

### Agent: venue_routes
**Blueprint:** `venues_bp` (name `venues`, url_prefix `/venues`)
**Files:**
- `app/venue_routes.py`
- `app/templates/venues/list.html`
- `app/templates/venues/detail.html`
- `app/templates/venues/form.html`

**Responsibility:** Implements all venue routes (list, new, detail, edit, delete) and their Jinja2 templates; imports `count_gigs_by_venue`, `list_gigs_by_venue` from `app.gig_models` and `avg_energy_by_venue` from `app.outcome_models`.

---

### Agent: gig_models
**Blueprint:** none
**Files:**
- `app/gig_models.py`

**Responsibility:** Implements the `gigs` table DDL (`GIG_SCHEMA`, `init_gig_schema`), all gig CRUD functions (`create_gig`, `get_gig`, `list_gigs`, `update_gig`, `delete_gig`, `set_gig_status`), venue-scoped queries (`count_gigs_by_venue`, `list_gigs_by_venue`), and dashboard analytics queries (`count_played_gigs`, `total_revenue_cents`, `top_venues`, `recent_gigs`, `monthly_revenue`).

---

### Agent: gig_routes
**Blueprint:** `gigs_bp` (name `gigs`, url_prefix `/gigs`)
**Files:**
- `app/gig_routes.py`
- `app/templates/gigs/list.html`
- `app/templates/gigs/detail.html`
- `app/templates/gigs/form.html`

**Responsibility:** Implements all gig routes (list, new, detail, edit, delete, status transition) and their Jinja2 templates; imports `get_venue`, `list_venues` from `app.venue_models`, `get_outcome_by_gig_id` from `app.outcome_models`, `get_debrief_by_gig_id` from `app.debrief_models`, and `list_contacts_by_gig_id` from `app.contact_models`.

---

### Agent: outcome_models
**Blueprint:** none
**Files:**
- `app/outcome_models.py`

**Responsibility:** Implements the `outcomes` table DDL (`OUTCOME_SCHEMA`, `init_outcome_schema`), all outcome CRUD functions (`create_outcome`, `get_outcome_by_gig_id`, `update_outcome`), and analytics functions (`avg_energy_by_venue`, `avg_audience_energy`, `total_tips_cents`).

---

### Agent: outcome_routes
**Blueprint:** `outcomes_bp` (name `outcomes`, url_prefix `/outcomes`)
**Files:**
- `app/outcome_routes.py`
- `app/templates/outcomes/form.html`
- `app/templates/outcomes/detail.html`

**Responsibility:** Implements outcome routes (new, view, edit — no delete) and their Jinja2 templates; imports `get_gig` from `app.gig_models`.

---

### Agent: contact_models
**Blueprint:** none
**Files:**
- `app/contact_models.py`

**Responsibility:** Implements the `contacts` table DDL (`CONTACT_SCHEMA`, `init_contact_schema`), all contact CRUD functions (`create_contact`, `get_contact`, `list_contacts`, `update_contact`, `delete_contact`), and query functions (`list_follow_ups`, `list_contacts_by_gig_id`).

---

### Agent: contact_routes
**Blueprint:** `contacts_bp` (name `contacts`, url_prefix `/contacts`)
**Files:**
- `app/contact_routes.py`
- `app/templates/contacts/list.html`
- `app/templates/contacts/follow_ups.html`
- `app/templates/contacts/detail.html`
- `app/templates/contacts/form.html`

**Responsibility:** Implements all contact routes (list, follow-ups, new, detail, edit, delete) and their Jinja2 templates. MUST declare `/contacts/follow-ups` and `/contacts/new` BEFORE `/contacts/<id>` in source order to prevent Flask routing shadowing. Imports `get_gig`, `list_gigs` from `app.gig_models` and `get_venue`, `list_venues` from `app.venue_models`.

---

### Agent: debrief_models
**Blueprint:** none
**Files:**
- `app/debrief_models.py`

**Responsibility:** Implements the `debriefs` table DDL (`DEBRIEF_SCHEMA`, `init_debrief_schema`), all debrief CRUD functions (`create_debrief`, `get_debrief_by_gig_id`, `update_debrief`), and keyword search (`search_debriefs` — case-insensitive LIKE across raw_text, key_takeaways, lessons_learned, joined with gig date and venue name).

---

### Agent: debrief_routes
**Blueprint:** `debriefs_bp` (name `debriefs`, url_prefix `/debriefs`)
**Files:**
- `app/debrief_routes.py`
- `app/templates/debriefs/form.html`
- `app/templates/debriefs/detail.html`
- `app/templates/debriefs/search.html`

**Responsibility:** Implements all debrief routes (new, view, edit — no delete — and search) and their Jinja2 templates. MUST declare `/debriefs/search` BEFORE `/debriefs/<gig_id>` in source order. Imports `get_gig` from `app.gig_models` and `create_debrief`, `get_debrief_by_gig_id`, `update_debrief`, `search_debriefs` from `app.debrief_models`.

---

### Agent: dashboard
**Blueprint:** `dashboard_bp` (name `dashboard`, url_prefix `/dashboard`)
**Files:**
- `app/dashboard_routes.py`
- `app/templates/dashboard/index.html`

**Responsibility:** Implements the single dashboard route (`GET /dashboard/`) and its Jinja2 template, pulling all aggregation data from `app.gig_models` (`count_played_gigs`, `total_revenue_cents`, `top_venues`, `recent_gigs`, `monthly_revenue`) and `app.outcome_models` (`avg_audience_energy`, `total_tips_cents`).

---

STATUS: PASS

## 16. Known Pitfalls Applied

- **FC1 (naming divergence / CSRF parens):** Section 1 Export Names Table fixes
  every cross-boundary name; Section 4 rule 1 mandates `{{ csrf_token() }}` with
  parentheses in every POST form.
- **FC2 (Row vs scalar):** Section 1 usage examples explicitly mark each scalar
  function's return as int/float, not Row.
- **FC4/FC27 (date validation):** Section 6 adds explicit `re.match(r'^\d{4}-\d{2}-\d{2}$', value)`
  rows for gig date (create+edit) and contact follow_up_date.
- **FC7 (prefix doubling):** Section 4 rule 11 — route decorators relative to the
  blueprint url_prefix, never doubled.
- **FC10 (SECRET_KEY fallback):** Section 4 rule 2 — fail closed, `raise RuntimeError`,
  no dev fallback.
- **FC40 (per-connection PRAGMA / row_factory placement):** Section 4 rule 5 —
  canonical `get_db`, PRAGMA `foreign_keys = ON` on every connection, `row_factory`
  set only in `get_db`, never in models.
- **FC46 (phantom FK):** every `*_id` column in Section 3 DDL has `REFERENCES`.
- **FC47 (Markup XSS):** Section 4 rule 10 — custom filters must `markupsafe.escape`
  before `Markup()`; negative constraint against unescaped `Markup`.
- **FC48 (ghost files):** File Assignment Boundaries (Section 15) lists exactly the
  files each agent creates — nothing else; cleanup gate (Step 9w.9) enforces.
- **FC49 (smoke tests & DATABASE):** Section 4 rules 4 — `os.environ['DATABASE']` →
  `app.config['DATABASE']`, smoke tests use a tempfile, never `:memory:`.
- **Refinement Finding #1 (SESSION_COOKIE_SECURE):** Section 4 rule 3 — env-gated.
- **Refinement Finding #2 (`with conn:`):** Section 8 — `with conn:` is the only
  write pattern; no bare BEGIN/commit.
- **Refinement Finding #3 (Markup escape):** Section 4 rule 10 (same as FC47).
- **Refinement Finding #4 (date regex everywhere):** Section 6 enumerated rows.

## 17. Feed-Forward

- **Hardest decision:** Whether to run this as a 12-agent swarm given the brief is
  already a near-complete plan. Chose swarm because the explicit purpose is to
  validate the 3-stage context-death delegation architecture under realistic
  12-agent coordination load — not merely to ship a CRUD app. The traded-in risk is
  orchestrator context survival through inline deepen + 12-agent spawn, mitigated by
  the no-read discipline and the deepen-merge-runner / swarm-runner delegation stages.
- **Rejected alternatives:** FTS5 search (LIKE is sufficient, avoids FC36 MATCH
  operator-injection and tokenizer complexity); multi-user / user_id scoping now
  (YAGNI, would require compound unique constraints everywhere for zero current
  benefit); AI debrief parsing (PF-Intel owns voice→structure); solo build (defeats
  the architecture-validation purpose).
- **Least confident:** **Dashboard aggregation query correctness.** No prior solution
  doc covers the dashboard's paid-only revenue / GROUP BY / COALESCE logic. The
  deterministic fixture (3 played, $880 revenue, 4.5 avg energy, 8000 tips) is the
  verification anchor — the smoke test seeds it via POST routes and asserts the
  rendered dashboard totals. Reviewers should scrutinize the LEFT JOIN to outcomes
  (so paid gigs without outcomes still count their pay), the `payment_status = 'paid'`
  filter (so Gig 3's unpaid 45000 is excluded), and that `AVG(audience_energy)`
  averages over outcome rows (2), yielding 4.5 — not over gigs.
