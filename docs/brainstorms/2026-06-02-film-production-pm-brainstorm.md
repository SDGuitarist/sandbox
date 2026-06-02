---
date: 2026-06-02
topic: film-production-pm
---

# Film Production Project Management Tool

## What We're Building

A local-first Flask + SQLite web app for indie/mid-budget film producers that combines scheduling, call sheet generation, and budget tracking — the three pillars that StudioBinder, Movie Magic, and Yamdu each handle separately. Target: a single producer managing one production at a time, with 4 role levels (producer, AD, department head, crew member).

The app has 7 MVP features: project dashboard, crew & cast database, scene breakdown manager, shooting schedule with drag-and-drop (SortableJS), call sheet generator, budget tracker with department allocations, and Day Out of Days (DOOD) grid.

## Why This Approach

**Single-stack simplicity.** Flask + SQLite + Jinja2 is the sandbox standard. No JS build step. Bootstrap 5 dark theme for the film industry aesthetic (dark UIs are standard in production tools). SortableJS is the only JS dependency beyond Bootstrap, used exclusively for schedule strip reordering.

**16-agent vertical ownership.** Each blueprint gets its own agent with model + routes + templates. The model/route split pattern (proven at 29 agents with 0 merge conflicts in RestaurantOps) keeps file ownership clean. The database agent owns only schema.sql, database.py, and models/__init__.py — not model functions.

**Alternatives considered and rejected:**
- Node/Express: User specified Flask. No reason to deviate.
- Horizontal split (all models in one agent, all routes in another): Proven inferior at scale. Vertical ownership = fewer cross-boundary touches.
- Multi-project UI in Phase 1: The brief explicitly defers this. Schema keeps project_id for future support; UI stays single-production.

## Key Decisions

All 9 architecture decisions from the brief are resolved and final. The brainstorm's job is to answer the 3 open structural questions:

### Q1: Minimum shared-spec surface for 16 agents

The spec must prescribe (at minimum):
- **Export Names Table**: Every model function, blueprint name, url_for target, and route path that crosses agent boundaries. At 16 agents, this table will have ~80-100 entries.
- **Cross-Boundary Wiring Table**: Focus on the call sheet blueprint (consumes from 5-6 other modules). Budget/expense wiring is internal to those 2 agents. Schedule/callsheet wiring is the second-highest risk surface.
- **Coordinated Behaviors**: Flash message patterns, CSRF syntax (`{{ csrf_token() }}` with parens), money display filter (`| dollars`), date format filter, strip color CSS classes, base template block names, navbar link order.
- **Negative constraints (Do NOT rules)**: Do NOT use Bootstrap bg-* for strip colors. Do NOT store `remaining` in budget (always derived). Do NOT use Python datetime.now() (use SQL datetime('now')). Do NOT set conn.row_factory in model functions. Do NOT commit inside model functions unless the spec says "commits internally."
- **Transaction Contracts table with Error Handling column**: Every write function annotated with BEGIN IMMEDIATE + try/except/ROLLBACK or "does NOT commit."

### Q2: Highest cross-boundary coupling risk

**Call sheets are the highest risk.** A single call sheet generation pulls from schedule_models, cast_models, crew_models, location_models, scene_models, and department_models — 6 cross-boundary imports. If any consumed function has a name mismatch, missing export, or wrong return type, the call sheet page crashes. The brief already prescribes the exact 6 functions and their return types. The spec must include exact import paths.

Budget/expenses is second-highest risk but more self-contained (2 agents, not 6). Schedule is third — its coupling is primarily with callsheets (already covered) and the DOOD grid in reports.

**Resolution:** The call sheet Cross-Boundary Wiring Table must be the most detailed section of the spec, with exact function signatures, return types, and import paths. Budget/expense transaction rules need BEGIN IMMEDIATE prescriptions. Schedule needs the SortableJS class-name contract.

### Q3: Seeding-order dependency

Yes, there is a strict seeding order:
1. **departments** (seed 17 standard departments) — no FK dependencies
2. **budget_categories** (seed standard film template: ATL/BTL-Production/BTL-Post/Other) — no FK dependencies
3. **users** (seed at least one producer account for testing) — no FK dependencies
4. **projects** (seed one active production) — FK to users (created_by)
5. **project_members** (link seeded user to seeded project with role=producer) — FK to users, projects
6. **locations, cast_members, crew_members, scenes** — FK to projects

This seeding order must be locked in schema.sql (the database agent's file). Domain agents do NOT seed data — they consume what the database agent provides.

### Additional Key Decisions (from prior build lessons)

- **isolation_level=None** in database.py — mandatory for Flask+SQLite with manual BEGIN IMMEDIATE (from RestaurantOps)
- **PRAGMA set on every connection**: journal_mode=WAL, foreign_keys=ON, busy_timeout=5000 (from GigSheet FC40)
- **CSP header must include cdn.jsdelivr.net** for Bootstrap and SortableJS (from GigSheet FC38)
- **Every *_id column gets REFERENCES with ON DELETE** (from BrewOps FC46)
- **Logout must be POST with CSRF** (from RestaurantOps auth security checklist)
- **No hardcoded default passwords** (from RestaurantOps)
- **FTS5 search input sanitized**: strip operators, wrap in double quotes (from VenueConnect FC36)
- **Status badges use escape() before Markup()** (from Client Intake Dashboard FC47)

## Approach: 16-Agent Vertical Swarm

| # | Agent | Owns | Risk Level |
|---|-------|------|-----------|
| 1 | scaffold | app factory, base.html, static, CSS, filters, CSP | LOW |
| 2 | auth | login, registration, decorators, session | MEDIUM |
| 3 | projects | project CRUD, phase transitions, dashboard | LOW |
| 4 | scenes | scene breakdown CRUD, element tagging, status | LOW |
| 5 | cast | cast members, character assignments, scene M2M | LOW |
| 6 | crew | crew members, department assignments | LOW |
| 7 | departments | department list, head assignment, roster view | LOW |
| 8 | locations | location CRUD, permits, contact info | LOW |
| 9 | schedule | shoot days, scene-to-day, SortableJS reorder | HIGH |
| 10 | callsheets | generate from schedule+cast+crew+locations | HIGH |
| 11 | budget | categories, line items, allocation, top sheet | HIGH |
| 12 | expenses | expense logging, dept allocation enforcement | HIGH |
| 13 | reports | budget summary, DOOD grid, production progress | MEDIUM |
| 14 | search | FTS5 across scenes, cast, crew, locations | MEDIUM |
| 15 | database | schema.sql, database.py, seed data, models/__init__ | MEDIUM |
| 16 | tests | smoke tests + critical-flow tests from brief | MEDIUM |

## Open Questions

None. All architecture decisions are resolved in the brief. The 3 structural questions from the kickoff are answered above.

## Feed-Forward

- **Hardest decision:** Determining the seeding order and who owns it. The database agent must seed departments, budget categories, and a test user+project before any domain agent can function. This means the database agent's schema.sql is the single point of failure for all 15 other agents.
- **Rejected alternatives:** Having each domain agent seed its own test data (rejected because it creates FK ordering conflicts and duplicate seeds). Having a separate seed agent (rejected because it adds a 17th agent for a task that naturally belongs to the database agent).
- **Least confident:** Whether the call sheet Cross-Boundary Wiring Table will be detailed enough to prevent FC1/FC3 at runtime. Six cross-boundary imports is the densest coupling surface we've attempted. The spec must prescribe exact function signatures, return types, and import paths — but even with that, a single agent returning `list` instead of `list[dict]` could break the chain.

## Refinement Findings (from solution doc cross-reference)

5 gaps identified and incorporated:

1. **IDOR ownership checks (from VenueConnect):** Authorization Matrix must prescribe exact ownership check code per route, not just role decorators. VenueConnect found 5/8 P1s were IDOR.
2. **SortableJS cross-file flow trace (from Client Music Planner):** The class-name contract crosses 3 files (HTML attributes, JS selectors, Python field names). Flow-trace reviewer mandatory for schedule+callsheet surface.
3. **BEGIN IMMEDIATE scope (from RestaurantOps):** ALL status transitions need BEGIN IMMEDIATE, not just budget/expense. Scene status, call sheet status, and project phase transitions are all TOCTOU-vulnerable.
4. **FTS5 BEFORE triggers (from Prompting Dashboard Engine, Run 061):** FTS5 external-content sync triggers must use BEFORE DELETE and BEFORE UPDATE, not AFTER. AFTER triggers silently corrupt the index.
5. **Context exhaustion / tail delegation (from Tail Delegation, Run 061):** 16-agent build with 6 cross-boundary deepening targets will likely push orchestrator context high. Plan must invoke tail delegation (Step 17w).
