# Autopilot Brief: Film Production Project Management Tool

## App Description

Film production project management tool for indie/mid-budget producers. A local-first Flask + SQLite + Jinja2 web app that combines scheduling, call sheet generation, and budget tracking — the three pillars that StudioBinder, Movie Magic, and Yamdu each handle separately. Target user: a film producer managing a single production with 4 role levels (producer, assistant director, department head, crew member).

## MVP Features (Phase 1 — this build)

1. **Project Dashboard** — overview of current production: phase, key dates, budget spent vs total, scenes shot vs remaining
2. **Crew & Cast Database** — contacts with name, role, department, phone, email, rate. Cast members get character name and cast ID number. Filter by department.
3. **Scene Breakdown Manager** — all scenes with INT/EXT, location, DAY/NIGHT, page count (1/8ths), tagged elements (cast, props, wardrobe, SFX). Foundation for schedule and call sheets.
4. **Shooting Schedule / Stripboard** — order scenes into shoot days. Drag-and-drop reordering via SortableJS. Page count totals per day. Color coding: yellow=DAY/EXT, white=DAY/INT, blue=NIGHT/INT, green=NIGHT/EXT.
5. **Call Sheet Generator** — given a shoot day, auto-populate scenes (from schedule), cast (from breakdown), crew (from departments). Add call times and notes. Print/view as formatted page.
6. **Budget Tracker** — categories seeded from standard film template (ATL/BTL-Production/BTL-Post/Other). Line items with estimated vs actual amounts in integer cents. Running totals, variance, top sheet summary. Expense logging with department allocation enforcement.
7. **Day Out of Days (DOOD) Grid** — auto-generated from schedule + cast. Grid view: cast as rows, shoot days as columns, cells show W/SW/WF/SWF/H status.

## Out of Scope (Phase 2)

- Script import/parser (NLP problem)
- Shot lists and storyboards
- Document management (contracts, permits)
- Multi-project support
- Real-time collaboration / WebSocket
- Email/SMS call sheet distribution
- Vendor/rental tracking, petty cash
- Calendar sync, weather API
- Wrap reports, union compliance

## Tech Stack

Flask + SQLite + Jinja2 + Bootstrap 5 (dark theme) + SortableJS for drag-and-drop.
Spec template: docs/templates/shared-spec-flask.md

## Domain Context

### Production Phases
Development → Pre-Production → Production (Principal Photography) → Post-Production → Distribution/Release. A project's overall status is which phase it is in.

### Key Entities
Project, Scene (with INT/EXT, DAY/NIGHT, page count in 1/8ths), Breakdown Sheet (elements per scene), Shooting Schedule (scenes grouped by shoot day), Call Sheet (daily production document), Day Out of Days (cast x shoot day grid), Crew Member (name, role, department, rate), Cast Member (name, character, cast ID 1-99, agent), Location (name, address, permits, nearest hospital), Budget (categories, line items, actuals), Expense (vendor, amount, category, approved_by), Department (camera, sound, art, wardrobe, etc.)

### Standard Departments
Producing, Directing, Camera, Lighting/Electrical, Grip, Sound, Art/Production Design, Wardrobe/Costume, Hair & Makeup, Locations, Transportation, Stunts, SFX, VFX, Editorial/Post, Casting, Accounting. Seed as defaults.

### Budget Categories (Standard Film Template)
**Above-the-Line (ATL):** 1100 Story & Rights, 1200 Producer, 1300 Director, 1400 Cast
**Below-the-Line Production:** 2000-3400 (Production Staff, Extras, Art, Construction, Set Ops, SFX, Wardrobe, Makeup, Lighting, Camera, Sound, Transport, Locations, Media)
**Below-the-Line Post:** 4000-4500 (Editing, Music, Post Sound, Deliverables, VFX, Titles)
**Other:** 5000-5500 (Insurance, General, Publicity, Contingency 10%, Completion Bond, Overhead)
Model as BudgetCategory with account_number, name, parent_group. Seed defaults.

### Call Sheet Anatomy
**Header:** Production title, call sheet number, date, shoot day X of Y, weather, nearest hospital, crew call time.
**Schedule:** Scene number, description, cast IDs, D/N, INT/EXT, location, page count.
**Cast:** Cast ID, character/actor name, status (W/SW/WF/SWF/H), pickup/makeup/on-set times, remarks.
**Extras:** Count, call time, description.
**Department Notes:** Advance schedule, special instructions, walkie channels, meal times.
**Crew List:** Grouped by department — name, role, call time, phone.

### State Machines
**Production Phase:** development → pre_production → production → post_production → distribution (linear)
**Scene Status:** not_started → in_prep → ready → shooting → wrapped (with on_hold branching from in_prep/ready/shooting)

### Authorization Model
4 roles with cascading permissions:
- **Producer:** full access to everything including budget and admin
- **Assistant Director (AD):** schedule, callsheets, cast, crew, locations, reports. No budget write.
- **Department Head:** own department's crew, expenses (own dept only), callsheets (read). No budget allocation.
- **Crew Member:** own schedule, callsheets (read-only). No write access beyond own profile.

Project membership via project_members table (user_id, project_id, role). @require_project_member decorator on all project-scoped routes.

## Blueprint Architecture (~16 agents)

| # | Blueprint | url_prefix | Key Responsibility |
|---|-----------|------------|-------------------|
| 1 | scaffold | -- | App factory, base.html, static, CSS, init_db, get_db, filters |
| 2 | auth | /auth | Login, registration, role decorators, session management |
| 3 | projects | /projects | Film projects CRUD, phase transitions, dashboard |
| 4 | scenes | /scenes | Scene breakdown CRUD, element tagging, status transitions |
| 5 | cast | /cast | Cast members, character assignments, cast-to-scene M2M |
| 6 | crew | /crew | Crew members, department assignments, availability |
| 7 | departments | /departments | Department list, head assignment, crew roster view |
| 8 | locations | /locations | Location CRUD, permits, contact info |
| 9 | schedule | /schedule | Shoot days, scene-to-day assignment, drag-and-drop reorder |
| 10 | callsheets | /call-sheets | Generate from schedule+cast+crew+locations, formatted view |
| 11 | budget | /budget | Categories (seeded), line items, allocation, top sheet |
| 12 | expenses | /expenses | Expense logging, department allocation enforcement, approvals |
| 13 | reports | /reports | Budget summary, DOOD grid, production progress |
| 14 | search | /search | FTS5 across scenes, cast, crew, locations |
| 15 | database | -- | All model functions (shared module, not a blueprint) |
| 16 | tests | -- | Smoke tests for all routes |

## Highest-Risk Integration Surfaces

### Risk 1: Call Sheet Aggregation (FC3/FC1)
Call sheets consume data from 5-6 model modules simultaneously (schedule, cast, crew, locations, scenes, departments). Any name mismatch or missing export breaks the page. The Cross-Boundary Wiring Table MUST have a dedicated "Call Sheet Wiring" subsection with exact import paths and function signatures.

### Risk 2: Budget/Expense Transaction Integrity (FC29)
Creating an expense must atomically deduct from department budget. Deleting must restore. Without BEGIN IMMEDIATE, concurrent submissions corrupt totals. Every expense write function needs "requires BEGIN IMMEDIATE" annotation with try/commit/except/rollback wrapper prescribed in spec.

### Risk 3: Role-Based Authorization Matrix (FC35)
4 roles create ~60-80 authorization rows. Missing one row means a crew member sees budget data or a department head edits another department's expenses. Complete Authorization Matrix required. Negative smoke tests required ("crew cannot access budget").

## Applicable Patterns from Prior Builds

### From VenueConnect (25-agent, Run 049)
- Role-to-blueprint dashboard map: use DASHBOARD_MAP dict, never f-string interpolation with role values
- IDOR is #1 security finding in multi-role apps: @role_required checks WHO, ownership check verifies WHAT

### From RestaurantOps (29-agent, Run 052)
- Model/route split (2 agents per domain): 0 merge conflicts at 29 agents
- Coordinated Behaviors (10 code blocks): consistent UX across 14 blueprints
- All status transitions need BEGIN IMMEDIATE (TOCTOU on concurrent usage)
- isolation_level=None mandatory for Flask+SQLite with BEGIN IMMEDIATE

### From GigSheet (31-agent, Run 050)
- CSP must include CDN domains (SortableJS, Bootstrap) or JS silently dies
- SQLite PRAGMA busy_timeout is per-connection, not per-database
- FC37 fix: explicit "YOU MUST git add and git commit" in every agent brief

### From Client Music Planner (20-agent, Run 048)
- SortableJS drag-and-drop: data-id attribute + toArray() + JSON POST + batch UPDATE
- CSS class mismatch between template and JS is a cross-file bug only flow-trace catches

### From CoWorkFlow (22-agent, Run 055)
- CSRF token syntax ({{ csrf_token() }} with parens) must be in Coordinated Behaviors
- TOCTOU Fence: route UX gate + model authoritative check inside BEGIN IMMEDIATE

### From BrewOps (21-agent, Run 057)
- Derived state bypass via alternative transition path (FC45): verify ALL paths trigger side effects
- Phantom FK: every *_id column MUST have REFERENCES with ON DELETE behavior (FC46)

### From Client Intake Dashboard (15-agent, Run 058)
- Jinja2 Markup() bypasses auto-escape: every custom filter returning Markup must escape inputs (FC47)
- SECRET_KEY must fail closed (raise RuntimeError), not fall back to dev string

## Risk Injection (from agent-pitfalls.md)

### HIGH Priority Failure Classes
- **FC1** (Naming Divergence): 16 blueprints × cross-boundary names. Export Names Table with url_for targets mandatory.
- **FC4** (Validation Gap): Budget amounts need int-cents conversion, dates need format validation, role-restricted routes need ownership checks.
- **FC35** (IDOR): 4 roles with department-scoped data. Department heads must only see own department budget. Complete Authorization Matrix required.
- **FC29** (Transaction Boundaries): Budget allocation = multi-table write. Every expense write needs BEGIN IMMEDIATE + try/except/ROLLBACK.
- **FC3** (Dead Wiring): Call sheets consume from 5+ blueprints. Cross-Boundary Wiring Table with exact import paths.
- **FC43** (TOCTOU): Schedule conflict detection, budget allocation, scene status transitions all need re-check inside BEGIN IMMEDIATE.
- **FC36** (FTS5 Injection): Sanitize search input before MATCH (strip operators, wrap in quotes).
- **FC47** (Markup XSS): Status badges, role indicators — escape all variables before Markup().

### MEDIUM Priority
- **FC5** (Coordinated Behaviors): 16 agents independently deciding flash patterns, CSRF syntax, money display.
- **FC44** (Derived State): Expense updates must update department remaining balance in same transaction.
- **FC46** (Phantom FK): Every *_id column needs REFERENCES with ON DELETE.
- **FC38** (CSP-CDN): SortableJS + Bootstrap from CDN need inclusion in CSP header.
- **FC40** (PRAGMA per-connection): busy_timeout on every connection path.
- **FC37** (Agent no-commit): Brief must say "YOU MUST git add and git commit."

## Pre-Plan Design Decisions (Resolved)

1. **Project membership:** Yes — project_members table with (user_id, project_id, role). @require_project_member decorator.
2. **Call sheet data model:** Parent row (call_sheets) + child rows (call_sheet_entries per scene/cast). Multi-table write = BEGIN IMMEDIATE.
3. **Budget storage:** Integer cents. dollars template filter for display. round(float(val)*100) for parsing.
4. **Activity logging:** Deferred to Phase 2. Reduces spec complexity by ~15%.
5. **Department head assignment:** Foreign key departments.head_id -> users.id. Ownership checks use this.

## Swarm Configuration

- **Agent count:** 16 (vertical ownership, 2 per domain where applicable)
- **Spec template:** Flask shared spec with all 6 mandatory sections
- **Pre-swarm gates:** spec-consistency-checker + spec-completeness-checker
- **Plan frontmatter:** `swarm: true`
- **Tail delegation:** This is the first swarm build with the new tail-runner agent. Steps 17w-18w delegate the entire Shared Tail to a fresh context window.

## Monitoring (Tail Delegation Validation)

This build validates the tail delegation feature shipped earlier today. Monitor:
- Does the tail-runner agent complete all 10 steps?
- What is the tail-runner's context consumption at completion?
- Does the orchestrator reach Step 17w without context death?
- Are TAIL_SYNC_POINT markers still in sync?
