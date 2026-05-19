---
report: swarm-assignments
run: "046"
plan: docs/plans/solopreneur-command-center.md
date: 2026-05-19
validator: swarm-planner-agent
---

# Swarm Agent Assignment — Solopreneur Command Center

## Validation Summary

**Total agents:** 16
**Total files (directory structure):** 95
**Total files (agent table):** 96
**Duplicate assignments found:** 0
**Zero-file agents found:** 0
**Files with no agent owner:** 0
**Files in agent table not in directory structure:** 1 (see Gap Log below)

### Validation Result

STATUS: PASS (with one plan gap — see Gap Log)

The assignment is internally consistent. No file appears in two agents. No agent has zero files. All 95 files from the directory structure are assigned to exactly one agent.

One gap exists between the directory structure and the agent table: `command-center/app/templates/reports/index.html` is assigned to the `reports` agent and referenced in the render context (`render_template('reports/index.html')`) and the endpoint registry (`reports.index` GET /), but it is NOT listed in the directory structure tree (lines 165–171 of the plan). This is a plan authoring error — the file must be built. The assignment itself is correct; the directory structure must be updated.

---

## Gap Log

| File | Agent | In Directory Structure | In Agent Table | In Render Context | In Endpoint Registry |
|------|-------|----------------------|---------------|-------------------|---------------------|
| `command-center/app/templates/reports/index.html` | reports | NO | YES | YES | YES (reports.index) |

**Resolution:** The `reports` agent MUST create this file. The plan's directory structure section is missing it. This is a P1 plan gap — if the agent only builds what is in the directory structure, the `reports.index` route will fail with a TemplateNotFound error.

---

## Data Ownership Consistency Check

| Table | Writer Agent(s) in Plan | Agent(s) Own the Writer Files | Consistent? |
|-------|------------------------|------------------------------|-------------|
| user | auth | auth owns `app/auth/routes.py` | YES |
| business_profile | auth, settings | auth owns auth routes; settings owns settings routes | YES |
| company | companies | companies owns `app/companies/routes.py` | YES |
| contact | contacts | contacts owns `app/contacts/routes.py` | YES |
| interaction | contacts | contacts owns `app/contacts/routes.py` | YES |
| deal | pipeline | pipeline owns `app/pipeline/routes.py` | YES |
| project | projects | projects owns `app/projects/routes.py` | YES |
| milestone | projects | projects owns `app/projects/routes.py` | YES |
| task | tasks | tasks owns `app/tasks/routes.py` | YES |
| time_entry | time-tracking | time-tracking owns `app/time_tracking/routes.py` | YES |
| income | revenue | revenue owns `app/revenue/routes.py` | YES |
| expense | revenue | revenue owns `app/revenue/routes.py` | YES |
| income_category | core-infra (seed), settings | core-infra owns `schema.sql`; settings owns settings routes | YES |
| expense_category | core-infra (seed), settings | core-infra owns `schema.sql`; settings owns settings routes | YES |
| goal | goals | goals owns `app/goals/routes.py` | YES |
| journal_entry | notes | notes owns `app/notes/routes.py` | YES |
| note | notes | notes owns `app/notes/routes.py` | YES |
| activity_log | ALL modules | each module agent owns its routes.py | YES |
| project_template | projects | projects owns `app/projects/routes.py` | YES |
| template_milestone | projects | projects owns `app/projects/routes.py` | YES |
| template_task | projects | projects owns `app/projects/routes.py` | YES |
| notes_fts | notes | notes owns `app/notes/routes.py` + triggers in schema.sql | YES |
| journal_fts | notes | notes owns `app/notes/routes.py` + triggers in schema.sql | YES |

All 23 table ownership entries are consistent with agent file assignments.

---

## Swarm Agent Assignment

**Total agents:** 16
**Total files:** 96 (95 from directory structure + 1 plan gap file that must be created)
**Validation:** No file appears in multiple assignments

---

### Agent: core-infra

**Files:**
- `command-center/run.py`
- `command-center/config.py`
- `command-center/requirements.txt`
- `command-center/.gitignore`
- `command-center/app/__init__.py`
- `command-center/app/db.py`
- `command-center/app/models.py`
- `command-center/app/schema.sql`
- `command-center/app/decorators.py`
- `command-center/app/filters.py`

**File count:** 10

**Responsibility:** Build the app factory, database layer, all model functions, schema, decorators, and entry point — the foundation every other agent depends on.

**Data ownership:** Seeds `income_category` and `expense_category` tables via schema.sql. Owns `models.py` which all agents call but do not modify.

---

### Agent: auth

**Files:**
- `command-center/app/auth/__init__.py`
- `command-center/app/auth/routes.py`
- `command-center/app/templates/auth/login.html`
- `command-center/app/templates/auth/register.html`
- `command-center/app/templates/auth/setup.html`

**File count:** 5

**Responsibility:** Build login, registration, setup wizard, and logout routes plus their templates; write to `user` and `business_profile` tables.

**Data ownership:** Writer for `user` table and initial `business_profile` row (setup wizard).

---

### Agent: layout-static

**Files:**
- `command-center/app/templates/base.html`
- `command-center/app/templates/sidebar.html`
- `command-center/app/templates/_flash_messages.html`
- `command-center/app/templates/_quick_add_contact_modal.html`
- `command-center/app/templates/_quick_add_task_modal.html`
- `command-center/app/static/css/style.css`
- `command-center/app/static/js/app.js`
- `command-center/app/static/js/timer.js`
- `command-center/app/static/js/pipeline.js`
- `command-center/app/static/js/sort.js`

**File count:** 10

**Responsibility:** Build the shared base template, sidebar navigation, flash message partial, quick-add modals, global CSS, and all JavaScript modules.

**Data ownership:** Pure UI layer — no database writes.

---

### Agent: contacts

**Files:**
- `command-center/app/contacts/__init__.py`
- `command-center/app/contacts/routes.py`
- `command-center/app/templates/contacts/list.html`
- `command-center/app/templates/contacts/detail.html`
- `command-center/app/templates/contacts/form.html`

**File count:** 5

**Responsibility:** Build contact CRUD, interaction logging, and quick-add endpoint plus all contact templates.

**Data ownership:** Writer for `contact` and `interaction` tables.

---

### Agent: companies

**Files:**
- `command-center/app/companies/__init__.py`
- `command-center/app/companies/routes.py`
- `command-center/app/templates/companies/list.html`
- `command-center/app/templates/companies/detail.html`
- `command-center/app/templates/companies/form.html`

**File count:** 5

**Responsibility:** Build company CRUD routes and templates.

**Data ownership:** Writer for `company` table.

---

### Agent: pipeline

**Files:**
- `command-center/app/pipeline/__init__.py`
- `command-center/app/pipeline/routes.py`
- `command-center/app/templates/pipeline/board.html`
- `command-center/app/templates/pipeline/list.html`
- `command-center/app/templates/pipeline/detail.html`
- `command-center/app/templates/pipeline/form.html`
- `command-center/app/templates/pipeline/stats.html`

**File count:** 7

**Responsibility:** Build deal CRUD, Kanban board, stage movement, and pipeline stats routes and templates.

**Data ownership:** Writer for `deal` table.

---

### Agent: projects

**Files:**
- `command-center/app/projects/__init__.py`
- `command-center/app/projects/routes.py`
- `command-center/app/templates/projects/list.html`
- `command-center/app/templates/projects/detail.html`
- `command-center/app/templates/projects/form.html`
- `command-center/app/templates/projects/templates.html`

**File count:** 6

**Responsibility:** Build project CRUD, milestone management, template save/apply, and create-from-deal flow.

**Data ownership:** Writer for `project`, `milestone`, `project_template`, `template_milestone`, and `template_task` tables.

---

### Agent: tasks

**Files:**
- `command-center/app/tasks/__init__.py`
- `command-center/app/tasks/routes.py`
- `command-center/app/templates/tasks/list.html`
- `command-center/app/templates/tasks/my_day.html`
- `command-center/app/templates/tasks/form.html`

**File count:** 5

**Responsibility:** Build task CRUD, My Day view, task completion, quick-add, and recurring task scaffolding.

**Data ownership:** Writer for `task` table.

---

### Agent: time-tracking

**Files:**
- `command-center/app/time_tracking/__init__.py`
- `command-center/app/time_tracking/routes.py`
- `command-center/app/templates/time_tracking/entries.html`
- `command-center/app/templates/time_tracking/timesheet.html`

**File count:** 4

**Responsibility:** Build time entry CRUD, weekly timesheet view, and timer start/stop API endpoints.

**Data ownership:** Writer for `time_entry` table.

---

### Agent: revenue

**Files:**
- `command-center/app/revenue/__init__.py`
- `command-center/app/revenue/routes.py`
- `command-center/app/templates/revenue/income_list.html`
- `command-center/app/templates/revenue/income_form.html`
- `command-center/app/templates/revenue/expense_list.html`
- `command-center/app/templates/revenue/expense_form.html`
- `command-center/app/templates/revenue/pl.html`

**File count:** 7

**Responsibility:** Build income and expense CRUD, P&L view, and by-client/by-month revenue breakdown routes and templates.

**Data ownership:** Writer for `income` and `expense` tables.

---

### Agent: goals

**Files:**
- `command-center/app/goals/__init__.py`
- `command-center/app/goals/routes.py`
- `command-center/app/templates/goals/index.html`
- `command-center/app/templates/goals/history.html`

**File count:** 4

**Responsibility:** Build monthly goal tracking, target update, and history views.

**Data ownership:** Writer for `goal` table.

---

### Agent: notes

**Files:**
- `command-center/app/notes/__init__.py`
- `command-center/app/notes/routes.py`
- `command-center/app/templates/notes/journal.html`
- `command-center/app/templates/notes/list.html`
- `command-center/app/templates/notes/form.html`
- `command-center/app/templates/notes/search_results.html`

**File count:** 6

**Responsibility:** Build daily journal, note CRUD, and FTS5-powered note search routes and templates.

**Data ownership:** Writer for `note`, `journal_entry`, `notes_fts`, and `journal_fts` tables.

---

### Agent: reports

**Files:**
- `command-center/app/reports/__init__.py`
- `command-center/app/reports/routes.py`
- `command-center/app/templates/reports/index.html`
- `command-center/app/templates/reports/revenue.html`
- `command-center/app/templates/reports/client.html`
- `command-center/app/templates/reports/time.html`
- `command-center/app/templates/reports/pipeline.html`
- `command-center/app/templates/reports/utilization.html`
- `command-center/app/templates/reports/expense.html`

**File count:** 9

**Responsibility:** Build all 6 analytical reports, CSV export, and the reports index landing page.

**PLAN GAP NOTE:** `command-center/app/templates/reports/index.html` is assigned here and required by the `reports.index` endpoint, but it is missing from the plan's directory structure section. This agent MUST create this file.

**Data ownership:** Read-only consumer — queries contact, project, task, deal, time_entry, income, expense tables but writes to none of them.

---

### Agent: search

**Files:**
- `command-center/app/search/__init__.py`
- `command-center/app/search/routes.py`
- `command-center/app/templates/search/results.html`

**File count:** 3

**Responsibility:** Build global full-text search across contacts, projects, tasks, deals, and notes, plus the JSON API endpoint.

**Data ownership:** Read-only consumer — queries contact, project, task, deal, note, journal_entry via FTS5.

---

### Agent: settings

**Files:**
- `command-center/app/settings/__init__.py`
- `command-center/app/settings/routes.py`
- `command-center/app/templates/settings/profile.html`
- `command-center/app/templates/settings/financial.html`
- `command-center/app/templates/settings/targets.html`
- `command-center/app/templates/settings/categories.html`
- `command-center/app/templates/settings/export.html`

**File count:** 7

**Responsibility:** Build business profile editing, financial settings, revenue targets, category management, and full data export.

**Data ownership:** Writer for `business_profile` (updates), `income_category`, and `expense_category` tables.

---

### Agent: dashboard

**Files:**
- `command-center/app/dashboard/__init__.py`
- `command-center/app/dashboard/routes.py`
- `command-center/app/templates/dashboard/index.html`

**File count:** 3

**Responsibility:** Build the main dashboard view aggregating revenue snapshot, project summary, pipeline summary, overdue tasks, upcoming deadlines, hours this week, cash flow, and recent activity.

**Data ownership:** Read-only consumer — queries income, expense, project, deal, task, milestone, time_entry, activity_log, business_profile, goal tables but writes to none of them.

---

## Duplicate Scan Results

Every file path was checked against all other agent assignments. Result: **zero duplicates**.

The following files had the highest duplicate risk and were explicitly verified as assigned to exactly one agent:

| File | Assigned To | Also in Another Agent? |
|------|-------------|----------------------|
| `command-center/app/__init__.py` | core-infra | NO |
| `command-center/app/models.py` | core-infra | NO |
| `command-center/app/schema.sql` | core-infra | NO |
| `command-center/app/templates/base.html` | layout-static | NO |
| `command-center/app/templates/sidebar.html` | layout-static | NO |
| `command-center/app/static/js/app.js` | layout-static | NO |
| `command-center/app/static/js/pipeline.js` | layout-static | NO |

---

## File Count by Agent

| Agent | File Count |
|-------|-----------|
| core-infra | 10 |
| auth | 5 |
| layout-static | 10 |
| contacts | 5 |
| companies | 5 |
| pipeline | 7 |
| projects | 6 |
| tasks | 5 |
| time-tracking | 4 |
| revenue | 7 |
| goals | 4 |
| notes | 6 |
| reports | 9 |
| search | 3 |
| settings | 7 |
| dashboard | 3 |
| **TOTAL** | **96** |

---

## Action Items Before Launch

1. **Fix plan directory structure:** Add `command-center/app/templates/reports/index.html` to the directory structure tree under `reports/` (between `expense.html` and the closing of the reports block). This brings the directory structure from 95 to 96 files and eliminates the gap.

2. **Inject pitfalls:** Per CLAUDE.md global instructions, read `~/.claude/docs/agent-pitfalls.md` and append the Known Pitfalls block to each agent's brief before launch.

3. **Copy BUILD_TRACKING.md:** Copy `~/.claude/docs/autopilot-tracking-template.md` to `command-center/BUILD_TRACKING.md` before agents start.

4. **Activity log wiring reminder:** The plan's highest-risk item (Feed-Forward section) is activity_log wiring. 12 of 16 agents must independently INSERT into activity_log. Flag this in every agent brief that owns a write route.

---

STATUS: PASS
