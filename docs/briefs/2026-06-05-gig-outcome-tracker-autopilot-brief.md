# Autopilot Brief: Gig Outcome Tracker

## One-Line Description

Flask + SQLite web app for musicians to log gig outcomes (audience response,
set list performance, contacts made, lessons learned, revenue) and build a
searchable intelligence database over time.

## Why This Build

This is the first swarm build after implementing the 3-stage context-death
delegation architecture (no-read discipline + deepen-merge-runner +
swarm-runner). The primary goal is to validate that architecture works on a
real 12-agent build. The secondary goal is to build an app that feeds Alex's
Performance Intelligence Protocol — codifying 30 years of tacit knowledge
about reading rooms, choosing music, and building venue relationships.

## User Story

After every gig, Alex sits in his car and records voice notes about the
experience. Currently this feeds PF-Intel (voice → structured venue/contact
data). But PF-Intel focuses on venue intelligence — it doesn't track what
actually happened during the performance: which songs worked, how the audience
responded, what energy shifts occurred, what contacts were made, and what
lessons were learned.

The Gig Outcome Tracker fills that gap. It captures the performance story:
what was planned vs. what actually happened, and what was learned.

## Core Workflow

1. **Before the gig:** Create a venue (if new). Create a gig entry (date,
   venue, event type, client, planned set list, expected pay).
2. **After the gig:** Mark gig as "played." Fill in the outcome form —
   audience energy, song highlights, audience feedback, staff feedback,
   tips, contacts made. Write a debrief (paste transcript or type notes).
3. **Manage contacts:** Add contacts met at a gig. Flag follow-ups. Review
   follow-up list.
4. **Over time:** Browse gig history, search debriefs, see venue performance
   patterns on venue detail pages, track revenue on the dashboard.
5. **Edit/correct:** Edit any venue, gig, contact, outcome, or debrief.
   Delete venues (only if no gigs), gigs (only if status is upcoming),
   contacts (always allowed).

## Feature Scope

### In Scope (this build)

- **Auth:** Register, login, logout. Single-user app — auth provides session
  security only. No user_id column on domain tables (unnecessary scoping for
  a single-user app; add in future mesh phase if multi-user is needed).
- **Venues:** Create, list, detail, edit, delete (restricted). Fields: name,
  location, venue_type, capacity_estimate, vibe_notes, notes. Venue detail
  shows gig history and average audience energy at that venue.
- **Gigs:** Create, list, detail, edit, delete (restricted to upcoming only),
  status transitions. Fields: date, venue_id, event_type, client_name,
  client_email, planned_set_summary, expected_pay_cents, actual_pay_cents,
  payment_status, status, notes. Gig detail is the hub page — links to
  outcome entry/view, debrief entry/view, venue, and contacts met here.
- **Outcomes:** Create, view, edit (one per gig, 1:1). Fields:
  audience_energy (1-5), audience_size_estimate, song_highlights,
  song_struggles, audience_feedback, staff_feedback, personal_reflections,
  tips_cents, leads_generated, overall_rating (1-5). No delete — edit to
  correct.
- **Contacts:** Create, list, detail, edit, delete. Fields: name, role,
  organization, phone, email, met_at_gig_id, venue_id, follow_up_needed,
  follow_up_date, follow_up_notes, notes. Dedicated follow-up list view
  (contacts where follow_up_needed = true, sorted by follow_up_date).
- **Debriefs:** Create, view, edit (one per gig, 1:1). Fields: raw_text,
  key_takeaways, lessons_learned. No AI parsing — just text storage. Search
  across all debriefs by keyword.
- **Dashboard:** Read-only overview with prescribed calculations (see
  Dashboard Calculations section below).

### Out of Scope (future phases)

- Voice recording / Whisper transcription (PF-Intel handles this)
- AI parsing of debrief text into structured fields (future)
- Integration with PF-Intel, GigPrep, LiveRequest, Lead Responder (future mesh)
- Set list management with individual songs (GigPrep handles this)
- Real-time audience interaction (LiveRequest handles this)
- Export / API endpoints (future)
- Multi-user / user_id scoping (future mesh phase)

## Data Model

```sql
-- All IDs are 8-character UUID hex prefixes (uuid4().hex[:8])
-- All timestamps are TEXT DEFAULT (datetime('now'))
-- Money is always in cents (integer, >= 0)

CREATE TABLE venues (
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

CREATE TABLE gigs (
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
  -- Both pay columns and payment_status set together or all NULL
  CHECK(
    (actual_pay_cents IS NULL AND payment_status IS NULL)
    OR (actual_pay_cents IS NOT NULL AND payment_status IS NOT NULL)
  )
);

CREATE TABLE outcomes (
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

CREATE TABLE contacts (
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

CREATE TABLE debriefs (
  id TEXT PRIMARY KEY,
  gig_id TEXT NOT NULL UNIQUE REFERENCES gigs(id) ON DELETE RESTRICT,
  raw_text TEXT NOT NULL,
  key_takeaways TEXT,
  lessons_learned TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
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

- **Venues:** Only deletable when no gigs reference them (RESTRICT enforces).
- **Gigs:** Only deletable when status = 'upcoming' AND no outcome AND no
  debrief exist (RESTRICT on outcomes/debriefs enforces the data side;
  route must check status = 'upcoming').
- **Contacts:** Always deletable.
- **Outcomes/Debriefs:** Not deletable (edit to correct).

## Data Model Conventions (Mesh Compatibility)

- **IDs:** 8-character UUID hex prefix (matches GigPrep). PF-Intel uses full
  UUIDs — the 8-char prefix maps later.
- **Dates:** ISO 8601 strings (YYYY-MM-DD for dates, datetime('now') for
  timestamps). Matches PF-Intel and GigPrep.
- **Money:** Always in cents (integer, >= 0). Two-column pattern from
  PF-Intel: amount_cents + payment_status with paired CHECK constraint.
- **No user_id:** Single-user app. Auth provides session security only. When
  mesh integration adds multi-user, add user_id + compound unique constraints.
- **No soft deletes:** YAGNI for this build.

## Authorization Matrix

All routes require login except the auth routes themselves. The scaffold
agent implements a `@login_required` decorator; every blueprint route agent
applies it to all routes.

| Route Group | Auth | Notes |
|-------------|------|-------|
| GET/POST /auth/login | Public | Unauthenticated access |
| GET/POST /auth/register | Public | Unauthenticated access |
| POST /auth/logout | Login required | Session teardown |
| /venues/* | Login required | All CRUD + delete |
| /gigs/* | Login required | All CRUD + status + delete |
| /outcomes/* | Login required | Create, view, edit |
| /contacts/* | Login required | All CRUD + follow-ups + delete |
| /debriefs/* | Login required | Create, view, edit, search |
| /dashboard/ | Login required | Read-only |

Unauthenticated requests to protected routes redirect to `/auth/login`.
No role-based access control — single user, session-only auth.

## Agent Architecture (12 agents, model/route vertical split)

| # | Agent | Owns | Blueprint |
|---|-------|------|-----------|
| 1 | scaffold | App factory, auth (register/login/logout), base templates, navbar, static CSS, get_db() | auth |
| 2 | venue_models | venues table DDL, venue CRUD functions, venue analytics functions | — |
| 3 | venue_routes | Venue create/list/detail/edit/delete routes + templates | venues |
| 4 | gig_models | gigs table DDL, gig CRUD functions, status transitions, revenue/analytics queries | — |
| 5 | gig_routes | Gig create/list/detail/edit/delete/status routes + templates | gigs |
| 6 | outcome_models | outcomes table DDL, outcome CRUD functions, energy analytics | — |
| 7 | outcome_routes | Outcome create/edit/view routes + templates (linked from gig detail) | outcomes |
| 8 | contact_models | contacts table DDL, contact CRUD functions, follow-up queries | — |
| 9 | contact_routes | Contact create/list/detail/edit/delete routes + templates, follow-up list | contacts |
| 10 | debrief_models | debriefs table DDL, debrief CRUD functions, keyword search | — |
| 11 | debrief_routes | Debrief create/edit/view routes + templates, search route | debriefs |
| 12 | dashboard | Dashboard aggregation queries + routes + template | dashboard |

## Cross-Boundary Wiring Table

These are the exact cross-module function calls agents must implement. Each
model agent defines these functions; each consuming route agent imports them.

| Consumer | Producer | Function Signature | Purpose |
|----------|----------|--------------------|---------|
| gig_routes | venue_models | `get_venue(conn, venue_id) -> Row\|None` | Show venue name on gig detail |
| gig_routes | outcome_models | `get_outcome_by_gig_id(conn, gig_id) -> Row\|None` | Show outcome link/summary on gig detail |
| gig_routes | debrief_models | `get_debrief_by_gig_id(conn, gig_id) -> Row\|None` | Show debrief link on gig detail |
| gig_routes | contact_models | `list_contacts_by_gig_id(conn, gig_id) -> list[Row]` | Show contacts met at this gig |
| venue_routes | gig_models | `count_gigs_by_venue(conn, venue_id) -> int` | Gig count on venue detail |
| venue_routes | outcome_models | `avg_energy_by_venue(conn, venue_id) -> float\|None` | Avg audience energy on venue detail |
| venue_routes | gig_models | `list_gigs_by_venue(conn, venue_id) -> list[Row]` | Gig history on venue detail |
| outcome_routes | gig_models | `get_gig(conn, gig_id) -> Row\|None` | Validate gig exists before outcome create |
| debrief_routes | gig_models | `get_gig(conn, gig_id) -> Row\|None` | Validate gig exists before debrief create |
| contact_routes | gig_models | `get_gig(conn, gig_id) -> Row\|None` | Show gig name on contact detail |
| contact_routes | venue_models | `get_venue(conn, venue_id) -> Row\|None` | Show venue name on contact detail |
| dashboard | gig_models | `count_played_gigs(conn) -> int` | Total gigs played |
| dashboard | gig_models | `total_revenue_cents(conn) -> int` | Total revenue (see Dashboard Calculations) |
| dashboard | gig_models | `top_venues(conn, limit=5) -> list[Row]` | Most-played venues |
| dashboard | gig_models | `recent_gigs(conn, limit=10) -> list[Row]` | Recent gigs with venue name |
| dashboard | gig_models | `monthly_revenue(conn, months=6) -> list[Row]` | Monthly revenue trend |
| dashboard | outcome_models | `avg_audience_energy(conn) -> float\|None` | Overall avg energy |
| dashboard | outcome_models | `total_tips_cents(conn) -> int` | Total tips |
| debrief_routes | debrief_models | `search_debriefs(conn, query) -> list[Row]` | Keyword search across all debriefs |

## Dashboard Calculations

All dashboard numbers use these exact queries:

```sql
-- Total gigs played
SELECT COUNT(*) FROM gigs WHERE status = 'played';

-- Total revenue (pay + tips, played gigs with payment_status = 'paid' only)
SELECT COALESCE(SUM(g.actual_pay_cents), 0) + COALESCE(SUM(o.tips_cents), 0)
FROM gigs g
LEFT JOIN outcomes o ON o.gig_id = g.id
WHERE g.status = 'played' AND g.payment_status = 'paid';

-- Average audience energy (all outcomes)
SELECT AVG(audience_energy) FROM outcomes;

-- Top 5 venues by gig count (played gigs only)
SELECT v.name, COUNT(g.id) as gig_count
FROM venues v JOIN gigs g ON g.venue_id = v.id
WHERE g.status = 'played'
GROUP BY v.id ORDER BY gig_count DESC LIMIT 5;

-- Recent 10 gigs (any status, newest first)
SELECT g.*, v.name as venue_name
FROM gigs g JOIN venues v ON g.venue_id = v.id
ORDER BY g.date DESC LIMIT 10;

-- Monthly revenue (last 6 months, pay + tips)
SELECT strftime('%Y-%m', g.date) as month,
       COALESCE(SUM(g.actual_pay_cents), 0) + COALESCE(SUM(o.tips_cents), 0) as total_cents
FROM gigs g
LEFT JOIN outcomes o ON o.gig_id = g.id
WHERE g.status = 'played' AND g.payment_status = 'paid'
  AND g.date >= date('now', '-6 months')
GROUP BY month ORDER BY month;

-- Total tips
SELECT COALESCE(SUM(tips_cents), 0) FROM outcomes;
```

## Template Structure

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

## Navigation

Navbar: **Dashboard** | **Gigs** | **Venues** | **Contacts** | **Logout**

Gig detail page is the hub — shows:
- Gig info + edit/delete buttons (delete only if upcoming + no outcome/debrief)
- Status transition button (upcoming→played, upcoming→cancelled)
- Outcome: "Add Outcome" button if none exists, or link to view/edit
- Debrief: "Add Debrief" button if none exists, or link to view/edit
- Contacts: list of contacts met at this gig + "Add Contact" link
- Venue: link to venue detail

## Routes

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

## Smoke Test Routes

| Method | Path | Expected Status | Notes |
|--------|------|-----------------|-------|
| GET | /auth/login | 200 | |
| POST | /auth/register | 302 → /auth/login | Valid registration |
| POST | /auth/login | 302 → /dashboard/ | Valid login |
| GET | /venues/ | 200 | Authenticated |
| POST | /venues/new | 302 → /venues/\<id\> | Valid venue |
| GET | /venues/\<id\> | 200 | |
| POST | /venues/\<id\>/edit | 302 → /venues/\<id\> | Valid edit |
| GET | /gigs/ | 200 | |
| POST | /gigs/new | 302 → /gigs/\<id\> | Valid gig |
| GET | /gigs/\<id\> | 200 | Hub page |
| POST | /gigs/\<id\>/edit | 302 → /gigs/\<id\> | Valid edit |
| POST | /gigs/\<id\>/status | 302 → /gigs/\<id\> | upcoming→played |
| POST | /outcomes/\<gig_id\>/new | 302 → /outcomes/\<gig_id\> | Valid outcome |
| POST | /outcomes/\<gig_id\>/edit | 302 → /outcomes/\<gig_id\> | Valid edit |
| GET | /contacts/ | 200 | |
| POST | /contacts/new | 302 → /contacts/\<id\> | Valid contact |
| GET | /contacts/follow-ups | 200 | |
| POST | /debriefs/\<gig_id\>/new | 302 → /debriefs/\<gig_id\> | Valid debrief |
| GET | /debriefs/search?q=test | 200 | Search results |
| GET | /dashboard/ | 200 | |
| POST | /gigs/\<id\>/delete | 302 → /gigs/ | Upcoming gig, no outcome/debrief |
| POST | /venues/\<id\>/delete | 302 → /venues/ | Venue with no gigs |
| POST | /contacts/\<id\>/delete | 302 → /contacts/ | Any contact |

## Validation Rules

| Route | Input | Validation | Error Response |
|-------|-------|------------|----------------|
| POST /auth/register | username | Required, non-empty | Flash "Username is required" |
| POST /auth/register | password | Required, min 8 characters | Flash "Password must be at least 8 characters" |
| POST /auth/register | username | Must not already exist | Flash "Username already taken" |
| POST /venues/new | name | Required, non-empty | Flash "Venue name is required" |
| POST /venues/new | name | Must be unique (case-insensitive) | Flash "Venue already exists" |
| POST /venues/\<id\>/delete | — | Must have zero gigs (RESTRICT) | Flash "Cannot delete venue with gig history" |
| POST /gigs/new | date | Required, YYYY-MM-DD format (re.match) | Flash "Valid date required" |
| POST /gigs/new | venue_id | Required, must exist in venues | Flash "Venue not found" |
| POST /gigs/new | expected_pay_cents | If provided, integer >= 0 | Flash "Pay cannot be negative" |
| POST /gigs/new | payment_status | Not allowed on create (gig starts with no payment info) | Ignore silently |
| POST /gigs/\<id\>/edit | actual_pay_cents | If provided, integer >= 0 | Flash "Pay cannot be negative" |
| POST /gigs/\<id\>/edit | payment_status | Must be one of: unpaid, pending, paid | Flash "Invalid payment status" |
| POST /gigs/\<id\>/edit | actual_pay_cents + payment_status | Both provided or both empty. If actual_pay_cents is set, payment_status is required (and vice versa). On create, both start NULL. On edit, user sets both when payment is known. | Flash "Pay amount and status must be set together" |
| POST /gigs/\<id\>/status | new_status | Valid transition only (upcoming→played, upcoming→cancelled) | Flash "Invalid status transition" |
| POST /gigs/\<id\>/delete | — | Status must be 'upcoming', no outcome, no debrief | Flash "Can only delete upcoming gigs with no outcome or debrief" |
| POST /outcomes/\<gig_id\>/new | gig_id | Must exist in gigs | Flash "Gig not found" |
| POST /outcomes/\<gig_id\>/new | gig_id | Must not already have outcome | Flash "Outcome already exists for this gig" |
| POST /outcomes/\<gig_id\>/new | audience_energy | Required, integer 1-5 | Flash "Energy must be 1-5" |
| POST /outcomes/\<gig_id\>/new | overall_rating | Required, integer 1-5 | Flash "Rating must be 1-5" |
| POST /outcomes/\<gig_id\>/new | tips_cents | If provided, integer >= 0 | Flash "Tips cannot be negative" |
| POST /contacts/new | name | Required, non-empty | Flash "Contact name is required" |
| POST /contacts/new | met_at_gig_id | If provided, must exist in gigs | Flash "Gig not found" |
| POST /contacts/new | follow_up_date | If provided, YYYY-MM-DD format | Flash "Valid date required for follow-up" |
| POST /debriefs/\<gig_id\>/new | gig_id | Must exist in gigs | Flash "Gig not found" |
| POST /debriefs/\<gig_id\>/new | gig_id | Must not already have debrief | Flash "Debrief already exists for this gig" |
| POST /debriefs/\<gig_id\>/new | raw_text | Required, non-empty | Flash "Debrief text is required" |

## What Makes This Build Special

This is the first build validating the context-death delegation architecture:
1. **Stage 1 (no-read discipline):** Orchestrator reads gate reports with
   `limit: 1` on PASS.
2. **Stage 2 (deepen-merge-runner):** Deepening merge delegated to fresh
   context (swarm-only).
3. **Stage 3 (swarm-runner):** Assembly + verification (Steps 11w-16w)
   delegated to fresh context.

Success = fully unattended completion with `final_status: DONE` and
`manual_resume: false` in BUILD_TRACKING.md.

## Debrief Search Semantics

Search uses case-insensitive `LIKE` matching against `raw_text`,
`key_takeaways`, and `lessons_learned` columns. No FTS5.

```sql
-- search_debriefs(conn, query) implementation
SELECT d.*, g.date as gig_date, v.name as venue_name
FROM debriefs d
JOIN gigs g ON g.id = d.gig_id
JOIN venues v ON v.id = g.venue_id
WHERE d.raw_text LIKE '%' || ? || '%'
   OR d.key_takeaways LIKE '%' || ? || '%'
   OR d.lessons_learned LIKE '%' || ? || '%'
ORDER BY g.date DESC;
```

SQLite LIKE is case-insensitive for ASCII by default. The query parameter
is the raw user input — no wildcard injection risk because `?` binding
escapes it and the `%` wrapping is in the SQL, not the parameter.

## Dashboard Smoke Test Fixtures

To verify dashboard calculations deterministically, the smoke test must
seed known data before checking the dashboard. Use this fixture set:

```
Venue: "The Grand Ballroom"
Venue: "Sunset Lounge"

Gig 1: date=2026-05-01, venue=Grand Ballroom, status=played,
        actual_pay_cents=50000, payment_status=paid
  Outcome 1: audience_energy=4, tips_cents=5000, overall_rating=4

Gig 2: date=2026-05-15, venue=Sunset Lounge, status=played,
        actual_pay_cents=30000, payment_status=paid
  Outcome 2: audience_energy=5, tips_cents=3000, overall_rating=5

Gig 3: date=2026-06-01, venue=Grand Ballroom, status=played,
        actual_pay_cents=45000, payment_status=unpaid
  (no outcome)

Gig 4: date=2026-06-10, venue=Sunset Lounge, status=upcoming,
        expected_pay_cents=40000
  (no outcome)
```

**Expected dashboard values with this fixture:**
- Total gigs played: **3**
- Total revenue: **88000** cents ($880) — only Gigs 1+2 (paid). Gig 3 is
  unpaid so excluded. = (50000 + 5000) + (30000 + 3000) = 88000
- Average audience energy: **4.5** — (4 + 5) / 2 outcomes
- Top venues: Grand Ballroom (2 played), Sunset Lounge (1 played)
- Recent gigs: all 4 (newest first: Gig 4, 3, 2, 1)
- Total tips: **8000** cents — 5000 + 3000

The smoke test creates this fixture data via POST routes, then verifies the
dashboard page (GET /dashboard/) renders the expected totals. The exact
assertion method (string matching on rendered HTML) is left to the plan.

## Acceptance Criteria

- All 23 smoke test routes return expected status codes
- All 12 agents merge with zero conflicts
- Dashboard totals match fixture expectations (3 played, $880 revenue, 4.5 avg energy)
- Gig detail hub page shows outcome/debrief status and contact list
- Contact follow-up list shows only contacts with follow_up_needed = 1
- Venue detail shows gig count and average audience energy
- Delete restrictions enforced (venue with gigs blocked, gig with outcome blocked)
- Payment paired CHECK constraint enforced (actual_pay + status set together)
- Debrief search returns results matching keyword across raw_text, key_takeaways, lessons_learned (case-insensitive LIKE)
