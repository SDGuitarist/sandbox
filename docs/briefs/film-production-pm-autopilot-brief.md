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

**Derived state chain (must be in same transaction):**
- `create_expense` → UPDATE departments SET spent_cents = spent_cents + ? WHERE id = ?
- `delete_expense` → UPDATE departments SET spent_cents = spent_cents - ? WHERE id = ?
- `allocate_budget` → verify SUM(allocations) <= project.total_budget inside BEGIN IMMEDIATE

**Defense-in-depth:**

| Constraint | DB Layer | Model Layer | Route Layer |
|-----------|----------|-------------|-------------|
| Budget cannot go negative | `CHECK (remaining_cents >= 0)` | Verify inside BEGIN IMMEDIATE | Flash error before write |
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
| `create_schedule_entry(conn, project_id, scene_id, location_id, date, sort_order)` | BEGIN IMMEDIATE | YES | Re-check location/date conflict inside lock |
| `update_schedule_entry(conn, entry_id, ...)` | BEGIN IMMEDIATE | YES | Re-check conflicts on location/date change |
| `delete_schedule_entry(conn, entry_id)` | does NOT commit | NO | Caller controls (may be part of bulk operation) |
| `reorder_schedule(conn, project_id, date, ordered_ids)` | BEGIN IMMEDIATE | YES | Batch UPDATE sort_order for all entries |
| `get_schedule_entries(conn, project_id, date)` | none (read-only) | N/A | Consumed by callsheets |
| `get_scenes_for_day(conn, project_id, date)` | none (read-only) | N/A | Consumed by callsheets, reports |

**TOCTOU fence pattern for schedule conflict:**
```python
def create_schedule_entry(conn, project_id, scene_id, location_id, date, sort_order):
    try:
        conn.execute('BEGIN IMMEDIATE')
        # Authoritative conflict check INSIDE the lock
        conflicts = conn.execute('''
            SELECT id FROM schedule_entries
            WHERE project_id = ? AND location_id = ? AND shoot_date = ?
            AND scene_id != ?
        ''', (project_id, location_id, date, scene_id)).fetchall()
        if conflicts:
            conn.execute('ROLLBACK')
            return None  # caller flashes "Location already scheduled"
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
    <span class="badge bg-{{ entry['strip_color'] }}">{{ entry['page_count'] }}</span>
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
      body: JSON.stringify({order: ids})
    });
  }
});
```

**Critical:** `.schedule-item` in template MUST match `.schedule-item` in JS.
`.drag-handle` in template MUST match `.drag-handle` in JS. Client Music
Planner Run 048 had a P1 from exactly this mismatch (`btn-move-up` vs `.move-up`).

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
