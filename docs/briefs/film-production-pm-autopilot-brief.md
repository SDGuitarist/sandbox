# Autopilot Brief: Film Production Project Management Tool

## App Description

Film production project management tool for indie/mid-budget producers. A local-first Flask + SQLite + Jinja2 web app that combines scheduling, call sheet generation, and budget tracking — the three pillars that StudioBinder, Movie Magic, and Yamdu each handle separately. Target user: a film producer managing one production at a time, with 4 role levels (producer, assistant director, department head, crew member). Phase 1 supports one active production but keeps project_id scoping in the schema and queries for permission isolation and future multi-project support.

## MVP Features (Phase 1 — this build)

1. **Project Dashboard** — overview of current production: phase, key dates, budget spent vs total, scenes shot vs remaining
2. **Crew & Cast Database** — contacts with name, role, department, phone, email, rate. Cast members get character name and cast ID number. Filter by department.
3. **Scene Breakdown Manager** — all scenes with INT/EXT, location, DAY/NIGHT, page count (1/8ths), tagged elements (cast, props, wardrobe, SFX). Foundation for schedule and call sheets.
4. **Shooting Schedule / Stripboard** — order scenes into shoot days. Drag-and-drop reordering via SortableJS. Page count totals per day. Color coding via custom CSS classes: `.strip-day-ext` (yellow background), `.strip-day-int` (white/light), `.strip-night-int` (blue), `.strip-night-ext` (green). Do NOT use Bootstrap `bg-*` utilities — define these 4 classes in the app's CSS.
5. **Call Sheet Generator** — given a shoot day, auto-populate scenes (from schedule), cast (from breakdown), crew (from departments). Add call times and notes. Print/view as formatted page.
6. **Budget Tracker** — categories seeded from standard film template (ATL/BTL-Production/BTL-Post/Other). Line items with estimated vs actual amounts in integer cents. Running totals, variance, top sheet summary. Expense logging with department allocation enforcement.
7. **Day Out of Days (DOOD) Grid** — auto-generated from schedule + cast. Grid view: cast as rows, shoot days as columns, cells show W/SW/WF/SWF/H status.

**DOOD status derivation algorithm (must be prescribed exactly — do not leave to agents):**
For each cast member, find all shoot days where they appear in a scheduled scene:
- **W** (Work): a working day that is neither the first nor last working day
- **SW** (Start/Work): the cast member's first working day
- **WF** (Work/Finish): the cast member's last working day
- **SWF** (Start/Work/Finish): cast member works only one day (first == last)
- **H** (Hold): a non-working day that falls between the first and last working days (actor is on hold, not released)
- **blank**: day is outside the cast member's start-to-finish range

Logic: `working_days = set of dates where cast_member_id appears in schedule_entries via scene_cast`. Sort chronologically. First = SW, Last = WF, First == Last = SWF, between first and last but not in working_days = H, in working_days but not first/last = W.

## Out of Scope (Phase 2)

- Script import/parser (NLP problem)
- Shot lists and storyboards
- Document management (contracts, permits)
- Multi-project UI (project switcher, project list page). Schema supports it; UI deferred.
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

**Identity model:** `users` table holds login credentials and app-level identity. `crew_members` table has a nullable `user_id` FK to `users` — crew can exist in the database without having a login (e.g., day-hire extras). When `user_id` is set, that crew member can log in and see "my schedule." `cast_members` do NOT have user accounts in Phase 1 (actors don't log into this tool — their agent does). "Own profile" for crew means `crew_members.user_id == g.user['id']`.

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
| 15 | database | -- | Schema DDL, init_db, seed data, get_db, connection helpers. Does NOT own model functions. |
| 16 | tests | -- | Smoke tests (see Critical-Flow Tests below) |

**Model file ownership:** Each domain owns its own model file under `app/models/`.
The database agent owns `app/models/__init__.py` (re-exports), `app/database.py`
(get_db, init_db, seed), and `schema.sql`. Domain agents own their model files:
`scene_models.py`, `cast_models.py`, `crew_models.py`, `schedule_models.py`,
`callsheet_models.py`, `budget_models.py`, `expense_models.py`, `location_models.py`,
`department_models.py`, `project_models.py`, `auth_models.py`, `search_models.py`.

## High-Risk Blueprint Details

The 3 blueprints below have the densest cross-boundary wiring and the
highest P1 probability. The spec MUST prescribe their model functions,
wiring, and transaction behavior at this level of detail. Other blueprints
are straightforward CRUD and the deepening agents can fill in their specs.

### Call Sheets (Risk 1 — FC3/FC1: Cross-Boundary Aggregation)

The call sheet is the hardest integration surface in the app. A single
call sheet generation pulls from 5-6 model modules simultaneously. If any
consumed function has a name mismatch, missing export, or wrong return
type, the call sheet page crashes or renders incomplete data.

**Model functions this blueprint CONSUMES (must be in Cross-Boundary Wiring Table):**

| Function | Defined In | Return Type | What It Provides |
|----------|-----------|-------------|-----------------|
| `get_schedule_entries(conn, project_id, date)` | schedule_models | `list[dict]` | Scenes scheduled for this shoot day |
| `get_cast_for_scenes(conn, scene_ids)` | cast_models | `list[dict]` with cast_id, character, actor_name | Cast members needed for today's scenes |
| `get_crew_by_department(conn, project_id)` | crew_models | `list[dict]` grouped by department | Full crew list with call times |
| `get_location(conn, location_id)` | location_models | `dict` with name, address, hospital | Shooting location details |
| `get_scenes(conn, scene_ids)` | scene_models | `list[dict]` with scene_number, int_ext, day_night, page_count | Scene breakdown details |
| `get_departments(conn, project_id)` | department_models | `list[dict]` | Department names for crew grouping |

**Model functions this blueprint EXPORTS:**

| Function | Return Type | Consumed By |
|----------|-------------|------------|
| `generate_call_sheet(conn, project_id, date)` | `int` (call_sheet_id) | reports (for listing), routes (for display) |
| `get_call_sheet(conn, call_sheet_id)` | `dict` | routes (detail view) |
| `get_call_sheet_entries(conn, call_sheet_id)` | `list[dict]` | routes (detail view) |

**Transaction behavior:**
- `generate_call_sheet`: requires BEGIN IMMEDIATE (inserts call_sheets parent row + call_sheet_entries child rows atomically)
- `get_call_sheet`, `get_call_sheet_entries`: read-only, no transaction needed

**The spec must include exact import paths:**
```
from app.models.schedule_models import get_schedule_entries
from app.models.cast_models import get_cast_for_scenes
from app.models.crew_models import get_crew_by_department
from app.models.location_models import get_location
from app.models.scene_models import get_scenes
from app.models.department_models import get_departments
```

### Budget + Expenses (Risk 2 — FC29: Transaction Integrity)

Budget and expenses are tightly coupled — creating an expense must
atomically deduct from the department's allocation, and deleting must
restore it. This is the financial equivalent of inventory deduction
(the pattern that produced P1s in GigSheet and BrewOps).

**Budget model functions:**

| Function | Transaction | Commits? | Error Handling |
|----------|-------------|----------|----------------|
| `get_budget_summary(conn, project_id)` | none (read-only) | N/A | N/A |
| `get_department_allocation(conn, dept_id)` | none (read-only) | N/A | N/A |
| `allocate_budget(conn, project_id, dept_id, amount_cents)` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `update_line_item(conn, line_item_id, estimated_cents, actual_cents)` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `get_budget_categories(conn, project_id)` | none (read-only) | N/A | N/A |

**Expense model functions:**

| Function | Transaction | Commits? | Error Handling |
|----------|-------------|----------|----------------|
| `create_expense(conn, dept_id, amount_cents, vendor, date, category)` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `delete_expense(conn, expense_id)` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `approve_expense(conn, expense_id, approved_by)` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `get_expenses_for_department(conn, dept_id)` | none (read-only) | N/A | N/A |

**Budget columns (exact schema):**
- `department_budgets`: `allocated_cents` (set by producer), `spent_cents` (derived from expenses)
- Invariant: `spent_cents <= allocated_cents` (enforced at model layer inside BEGIN IMMEDIATE)
- `remaining` is always derived: `allocated_cents - spent_cents` (never stored, computed in queries/templates)

**Derived state chain (must be in same transaction):**
- `create_expense` → UPDATE department_budgets SET spent_cents = spent_cents + ? WHERE department_id = ?
- `delete_expense` → UPDATE department_budgets SET spent_cents = spent_cents - ? WHERE department_id = ?
- `allocate_budget` → verify SUM(allocated_cents) <= project.total_budget_cents inside BEGIN IMMEDIATE

**Defense-in-depth:**

| Constraint | DB Layer | Model Layer | Route Layer |
|-----------|----------|-------------|-------------|
| spent <= allocated | `CHECK (spent_cents <= allocated_cents)` | Verify inside BEGIN IMMEDIATE | Flash error before write |
| Expense amount positive | `CHECK (amount_cents > 0)` | Verify > 0 inside transaction | Flash error + int() try/except |
| Allocation <= total budget | -- (app-level) | SUM check inside BEGIN IMMEDIATE | Flash with remaining amount |

**Ownership checks (FC35):**
- Producer: can allocate any department, view all expenses
- Department head: can only create/view expenses for own department (`departments.head_id == g.user['id']`)
- AD, Crew: no budget/expense write access

### Schedule (Risk 3 — FC43: TOCTOU + SortableJS Wiring)

The schedule blueprint has two distinct risk surfaces: conflict detection
(TOCTOU when two users schedule the same location/time) and drag-and-drop
reordering (SortableJS CSS class matching).

**Model functions:**

| Function | Transaction | Commits? | Notes |
|----------|-------------|----------|-------|
| `create_schedule_entry(conn, project_id, scene_id, location_id, date, sort_order)` | BEGIN IMMEDIATE | YES | Re-check duplicate scene scheduling inside lock |
| `update_schedule_entry(conn, entry_id, ...)` | BEGIN IMMEDIATE | YES | Re-check duplicate scene scheduling on scene/date changes |
| `delete_schedule_entry(conn, entry_id)` | does NOT commit | NO | Caller controls (may be part of bulk operation) |
| `reorder_schedule(conn, project_id, date, ordered_ids)` | BEGIN IMMEDIATE | YES | Validate: all IDs belong to project+date, no missing/extra IDs vs DB set, require producer/AD role. Batch UPDATE sort_order. |
| `get_schedule_entries(conn, project_id, date)` | none (read-only) | N/A | Consumed by callsheets |
| `get_scenes_for_day(conn, project_id, date)` | none (read-only) | N/A | Consumed by callsheets, reports |

**TOCTOU fence pattern for duplicate-scene prevention:**

Multiple scenes at the same location on the same shoot day is normal in
film production (you shoot all scenes at a location in one day to save
travel time). The conflict to prevent is the SAME scene being scheduled
twice on different days.

```python
def create_schedule_entry(conn, project_id, scene_id, location_id, date, sort_order):
    try:
        conn.execute('BEGIN IMMEDIATE')
        # Prevent same scene scheduled on multiple days
        existing = conn.execute('''
            SELECT id, shoot_date FROM schedule_entries
            WHERE project_id = ? AND scene_id = ?
        ''', (project_id, scene_id)).fetchone()
        if existing:
            conn.execute('ROLLBACK')
            return None  # caller flashes "Scene already scheduled on [date]"
        conn.execute('INSERT INTO schedule_entries ...', (...))
        conn.execute('COMMIT')
        return new_id
    except Exception:
        conn.execute('ROLLBACK')
        raise
```

**SortableJS wiring (CSS class names MUST match between template and JS):**

Template (schedule routes agent):
```html
<div id="schedule-list" class="sortable-container">
  {% for entry in entries %}
  <div class="schedule-item" data-id="{{ entry['id'] }}">
    <span class="drag-handle">&#x2801;</span>
    Scene {{ entry['scene_number'] }} — {{ entry['location_name'] }}
    <span class="strip-badge {{ entry['strip_color_class'] }}">{{ entry['page_count'] }}</span>
  </div>
  {% endfor %}
</div>
```

JS (static/js):
```javascript
new Sortable(document.getElementById('schedule-list'), {
  handle: '.drag-handle',
  onEnd: function() {
    const ids = [...document.querySelectorAll('.schedule-item')]
      .map(el => el.dataset.id);
    fetch('/schedule/reorder', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
      body: JSON.stringify({order: ids, shoot_date: currentDate})
    });
  }
});
```

**Critical:** `.schedule-item` in template MUST match `.schedule-item` in JS.
`.drag-handle` in template MUST match `.drag-handle` in JS. Client Music
Planner Run 048 had a P1 from exactly this mismatch (`btn-move-up` vs `.move-up`).

`strip_color_class` must be one of: `strip-day-ext`, `strip-day-int`,
`strip-night-int`, `strip-night-ext`. Never construct arbitrary CSS class
names from unsanitized scene fields.

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

## Architecture Decisions (Resolved — do not revisit during planning)

These were identified as contradictions by Codex review and resolved before launch:

1. **Single-production vs multi-project:** Phase 1 uses one active production. Schema keeps `project_id` and `project_members` for permission scoping. Create/edit the single active project; no project index, no switcher, no multi-project navigation. Multi-project UI is Phase 2.
2. **Model file ownership:** Each domain owns its own model file (`app/models/scene_models.py`, etc.). The database agent owns ONLY `schema.sql`, `app/database.py` (get_db, init_db, seed), and `app/models/__init__.py` (re-exports). It does NOT own model functions.
3. **Schedule permits multiple scenes per location per day.** This is normal in film production. The conflict to prevent is the same scene scheduled on two different days (duplicate-scene check, not location-date uniqueness).
4. **Budget columns:** `department_budgets.allocated_cents` and `department_budgets.spent_cents`. `remaining` is always computed (`allocated_cents - spent_cents`), never stored. Invariant: `spent_cents <= allocated_cents`.
5. **DOOD derivation is algorithmic, not agent-interpreted.** The W/SW/WF/SWF/H algorithm is prescribed exactly in MVP Features above.
6. **Reorder endpoint validates full ID set.** Server checks: all IDs belong to current project and shoot date, no missing or extra IDs vs the database set, and requires producer/AD role.
7. **Crew identity:** `crew_members.user_id` is nullable FK to `users`. Crew without accounts exist in the database but can't log in. Cast members have no user accounts in Phase 1.
8. **Call sheet child tables:** `call_sheet_scenes` and `call_sheet_cast` — two separate tables, not one polymorphic table.
9. **Stripboard colors:** Custom CSS classes (`.strip-day-ext`, etc.), not Bootstrap `bg-*` utilities.

## Pre-Plan Design Decisions (Resolved)

1. **Project membership:** Yes — project_members table with (user_id, project_id, role). @require_project_member decorator.
2. **Call sheet data model:** Parent row (`call_sheets`) + two child tables: `call_sheet_scenes` (scene_id, sort_order — which scenes shoot that day) and `call_sheet_cast` (cast_member_id, call_time, makeup_time, on_set_time, status W/SW/WF/SWF/H, remarks). Crew call times are derived from department defaults, not stored per call sheet. Multi-table write = BEGIN IMMEDIATE.
3. **Budget storage:** Integer cents. dollars template filter for display. round(float(val)*100) for parsing.
4. **Activity logging:** Deferred to Phase 2. Reduces spec complexity by ~15%.
5. **Department head assignment:** Foreign key departments.head_id -> users.id. Ownership checks use this.

## Critical-Flow Tests (Required — not just "smoke tests for all routes")

The tests agent MUST include these specific test cases beyond basic route smoke tests:

1. **Call sheet generation:** Create project → add scenes → add cast to scenes → create schedule entries → generate call sheet → verify call sheet contains correct scenes, cast with statuses, and location
2. **DOOD grid:** Schedule 3 scenes across 5 days with overlapping cast → verify W/SW/WF/SWF/H statuses are correct for each cast member
3. **Budget overspend rejection:** Allocate 1000 cents to department → create expense for 1001 cents → verify rejection with flash message
4. **Expense rollback:** Create expense → verify spent_cents incremented → delete expense → verify spent_cents restored to original
5. **Department-head IDOR:** Log in as dept_head for Camera → attempt to create expense for Sound department → verify 403
6. **Crew-member budget IDOR:** Log in as crew member → attempt GET /budget → verify 403
7. **Schedule reorder validation:** POST /schedule/reorder with IDs from wrong project → verify rejection
8. **FTS5 sanitization:** Search with `")(DROP TABLE` → verify no 500, results returned safely
9. **CSRF on JSON POST:** POST /schedule/reorder without X-CSRFToken header → verify rejection (400 or 403) and order is not mutated
10. **CSP allows SortableJS:** Verify Content-Security-Policy response header includes `script-src` allowing cdn.jsdelivr.net (the Bootstrap and SortableJS CDN domain)

## Swarm Configuration

- **Agent count:** 16 (vertical ownership, 2 per domain where applicable)
- **Spec template:** Flask shared spec with all 6 mandatory sections
- **Pre-swarm gates:** spec-consistency-checker + spec-completeness-checker
- **Plan frontmatter:** `swarm: true`
- **Tail delegation:** This is the first swarm build with the new tail-runner agent. Steps 17w-18w delegate the entire Shared Tail to a fresh context window.

## Monitoring (Tail Delegation Validation)

This build validates the tail delegation feature shipped earlier today.
Note: a 16-agent feature-heavy app makes tail delegation failures harder
to attribute vs a smaller swarm. The app is the priority — tail delegation
validation is a secondary benefit. If the tail-runner fails, diagnose
whether the failure is tail-runner infrastructure or app-specific review
complexity before concluding the feature is broken.

Monitor:
- Does the tail-runner agent complete all 10 steps?
- What is the tail-runner's context consumption at completion?
- Does the orchestrator reach Step 17w without context death?
- Are TAIL_SYNC_POINT markers still in sync?
