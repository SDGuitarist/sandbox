---
name: Solopreneur Command Center Brainstorm
description: Full-stack Flask + SQLite + Jinja2 business operating system for solopreneurs
date: 2026-05-19
status: complete
feed_forward:
  risk: "15+ agent swarm coordination at this scale — cross-module data flows (deal→project, time→revenue) create integration wiring gaps"
  verify_first: true
---

# Solopreneur Command Center — Brainstorm

## Problem Statement

Solopreneurs (consultants, freelancers, coaches, fractional execs, indie developers) run their businesses across 5+ disconnected tools: Notion for notes, spreadsheets for finances, a basic CRM, a calendar app, a time tracker, and maybe an accounting app. No single tool combines CRM + pipeline + project management + time tracking + revenue tracking + reporting for a one-person business.

**The opportunity:** Build the single operating system for running a solo business. Once a user has 6+ months of revenue data, time logs, and client history, switching costs are extremely high — that's the moat. Priced at $29-59/mo with a free tier (3 projects, 5 contacts).

## Target User

Single solopreneur. Not teams, not enterprises. One person running everything:
- **Consultants** — need CRM, pipeline, time tracking, invoicing data
- **Freelance designers** — need project management, time tracking, client management
- **Coaches** — need CRM, scheduling data, revenue tracking
- **Fractional execs** — need pipeline, project tracking across multiple clients
- **Independent developers** — need project management, time tracking, revenue tracking

## Core Modules (13 total)

### 1. Authentication & Onboarding
- Email + password registration with bcrypt hashing
- Login/logout with Flask-Login session management
- First-time setup wizard: business name, your name, industry (dropdown: consulting, design, development, coaching, marketing, other), currency symbol, fiscal year start month
- Business profile: name, logo URL, tagline, email, phone, website, address, tax ID
- Profile info used in reports and CSV exports

### 2. Dashboard — The Single Pane of Glass
- Revenue snapshot: this month, last month, YTD, monthly target, % to target (progress bar)
- Active projects count with total value
- Pipeline summary: total deals, total pipeline value, deals closing this month
- Overdue tasks (red alert list — top 5)
- Upcoming deadlines next 7 days (tasks + project milestones)
- Hours logged this week vs weekly target
- Cash flow indicator: income this month minus expenses this month
- Recent activity feed (last 10 actions across all modules)
- Chart.js: revenue trend line (last 6 months), pipeline bar chart (value per stage)

### 3. CRM — Contacts & Companies
- Contact records: name, email, phone, company_id (FK), role/title, tags (comma-separated text), source (referral, website, social, cold_outreach, other), notes, status (lead, active_client, past_client, partner), created_at, updated_at
- Company records: name, website, industry, address, notes, created_at
- Company → contacts relationship (one company, many contacts)
- Contact list: search by name/email/company, filter by status and tags, sort by name/date added
- Contact detail page: profile info, linked projects, logged time, total revenue, interaction timeline
- Interaction log per contact: date, type (call, email, meeting, message), notes — manual entry
- Quick-add contact modal (accessible from any page)

### 4. Sales Pipeline
- Deal records: title, contact_id (FK), company_id (FK), value (integer cents), stage, probability_pct, expected_close_date, notes, source, loss_reason, created_at, updated_at
- Pipeline stages: lead(10%), discovery(25%), proposal_sent(50%), negotiation(65%), verbal_yes(80%), won(100%), lost(0%)
- Board view: CSS grid columns per stage, deal cards with title/value/contact, "Move to [stage]" buttons
- List view: sortable table with all deal fields
- Weighted pipeline value: sum of (value * probability_pct / 100) per stage
- Won flow: prompt to create project (pre-fills client, value from deal)
- Lost flow: require loss_reason (competitor, price, timing, ghosted, not_a_fit, other)
- Pipeline stats: total value per stage, weighted forecast, deals closing this month, win rate

### 5. Project Management
- Project records: name, contact_id (FK), status (not_started, in_progress, on_hold, completed, cancelled), type (fixed_price, hourly, retainer, pro_bono), value (integer cents), hourly_rate (integer cents), start_date, target_end_date, actual_end_date, description, notes, deal_id (FK, nullable), created_at, updated_at
- Project detail page: overview, milestones, tasks, time logged, financials (budget vs actual)
- Milestones: name, project_id (FK), due_date, status (pending, completed), description
- Project list: filter by status, client, type; sort by deadline, value, name
- Project templates: save project structure (milestones + default tasks) as template, create from template
- Budget tracking: fixed_price → budget vs (hours * rate); hourly → hours * rate = revenue

### 6. Task Management
- Task records: title, description, project_id (FK, nullable), priority (low, medium, high, urgent), status (todo, in_progress, done), due_date, estimated_hours, tags (comma-separated text), is_recurring, recurrence_interval (daily, weekly, monthly, custom), recurrence_days (integer), created_at, updated_at
- Task list: filter by project, priority, status, due date range; sort by due date, priority
- "My Day" view: tasks due today + overdue, ordered by priority (urgent first)
- Quick-add task modal (accessible from any page)
- Recurring tasks: when completed, auto-generate next instance based on interval
- Standalone tasks (no project) for general business admin

### 7. Time Tracking
- Time entry records: date, project_id (FK), task_id (FK, nullable), hours (stored as integer minutes for precision), description, billable (boolean), created_at
- Active timer: start_time stored in localStorage (vanilla JS), calculates duration on stop, creates time entry
- Manual time entry: date + hours + description + project + billable
- Weekly timesheet view: table with days as columns (Mon-Sun), projects as rows, hours in cells
- Time summary per project: total hours, billable hours, billable amount (hours * rate)
- Utilization rate: billable hours / total hours logged (weekly/monthly)
- Weekly hours target (configurable in settings, default 40)

### 8. Revenue & Expenses
- Income records: amount (integer cents), date, contact_id (FK, nullable), project_id (FK, nullable), category, payment_method (bank_transfer, card, cash, check, paypal, other), notes, created_at
- Expense records: amount (integer cents), date, category, vendor, notes, tax_deductible (boolean), created_at
- Income categories (default): project_payment, retainer, consulting, product_sale, other
- Expense categories (default): software, hardware, office, travel, marketing, education, contractor, other
- Monthly P&L view: income - expenses = profit, broken down by category
- Revenue by client: ranked table with total revenue, project count, avg project value
- Revenue by month: table with monthly income, expenses, profit, margin %
- YTD summary: total revenue, total expenses, profit, effective hourly rate, tax-deductible total

### 9. Goals & Targets
- Monthly revenue target (integer cents, configurable)
- Weekly hours target (integer, configurable)
- Quarterly revenue target (auto = 3x monthly, or manual override)
- Dashboard progress bars: current vs target for revenue and hours
- Goal history: track monthly actuals vs targets over time (table view)
- Goal records: month (YYYY-MM), revenue_target, hours_target, revenue_actual, hours_actual

### 10. Notes & Journal
- Journal entries: date (unique per day), content (textarea), created_at, updated_at
- Standalone notes: title, content, tags (comma-separated), created_at, updated_at
- Per-contact notes stored on contact record (notes field)
- Per-project notes stored on project record (notes field)
- Notes search: SQLite FTS5 full-text search across journal entries and standalone notes

### 11. Reports
- Revenue Report: monthly revenue table, filterable by date range and client
- Client Report: revenue by client, projects per client, avg project value, last interaction
- Time Report: hours by project, by week, by client; billable vs non-billable breakdown
- Pipeline Report: win rate, avg deal size, avg time to close, revenue forecast
- Utilization Report: weekly utilization rate over time, target vs actual
- Expense Report: expenses by category, monthly trend, tax-deductible total
- All reports: CSV export button (one file per report)

### 12. Global Search
- Search bar in nav sidebar, always visible
- Searches across: contacts (name, email, company), projects (name), tasks (title), deals (title), notes (content via FTS5)
- Results grouped by type with direct links
- Keyboard shortcut: "/" focuses the search bar
- Vanilla JS: fetch to /search?q=term, render results in dropdown

### 13. Settings
- Business profile (name, logo URL, address, email, phone, website, tax ID)
- Financial defaults: default hourly rate (integer cents), currency symbol, fiscal year start month
- Targets: monthly revenue target, weekly hours target
- Categories: customize income and expense categories (add/remove)
- Data export: CSV export button per module (contacts, projects, tasks, time entries, income, expenses, deals, notes)

## Database Design Decisions

- **SQLite** with WAL mode (set once in init_db) + PRAGMA foreign_keys=ON per connection
- **Money as integer cents** — all monetary values stored as integers (cents). Display via Jinja2 `|dollars` filter. Form prefill via `'%.2f' % (cents / 100)`.
- **Time as integer minutes** — time entries store minutes, not decimal hours. Display as hours:minutes. Input accepts decimal hours, converts to minutes.
- **Tags as comma-separated text** — simplest approach for MVP. No junction table needed. Search with LIKE '%tag%'.
- **FTS5 for notes search** — virtual table for full-text search on journal entries and standalone notes.
- **Estimated tables:** User, BusinessProfile, Company, Contact, Interaction, Deal, Project, Milestone, Task, TimeEntry, Income, Expense, IncomeCategory, ExpenseCategory, Goal, JournalEntry, Note, ActivityLog, ProjectTemplate, TemplateMilestone, TemplateTask (21 tables)

## Tech Stack Decisions

- **Flask app factory pattern** with blueprints per module
- **flask-wtf** for CSRF — `csrf.init_app(app)` in factory, `{{ form.hidden_tag() }}` in templates
- **flask-login** for session management — `login_required` decorator on all non-auth routes
- **bcrypt** via werkzeug `generate_password_hash` / `check_password_hash`
- **Bootstrap 5 via CDN** — dark sidebar layout, NOT default Bootstrap look
- **Bootstrap Icons via CDN** — icon + label for each sidebar item
- **Chart.js via CDN** — revenue trend line, pipeline bar chart on dashboard
- **Vanilla JS** — timer (localStorage start time), global search (fetch + dropdown), stage-move buttons, quick-add modals
- **SECRET_KEY** from `os.environ.get('SECRET_KEY', secrets.token_hex(24))`

## UI/UX Decisions

- **Dark sidebar** (280px) with icon + label for each of 9 nav items: Dashboard, Contacts, Pipeline, Projects, Tasks, Time, Revenue, Reports, Settings
- **Light content area** with consistent card/table styling
- **Status badges** with color coding: green (active/done/won), yellow (in_progress/pending/discovery), red (overdue/urgent/lost), gray (inactive/cancelled/not_started)
- **Consistent table styling** across all list views with sortable column headers (vanilla JS sort)
- **Modals** for quick-add contact and quick-add task (Bootstrap 5 modal component)
- **Professional, dense UI** — power tool, not consumer app. Small fonts, compact spacing, lots of data visible

## Architecture: Swarm Agent Split

Vertical split by feature blueprint. Each agent owns one blueprint + its templates. Shared modules (db, models, app factory) owned by infrastructure agents. No cross-agent imports except through shared modules.

**Estimated: 16 agents**

1. **core-infra**: db.py, models.py, schema.sql, app/__init__.py, run.py, config.py
2. **auth**: auth blueprint, login/register/setup templates, decorators
3. **layout-static**: base.html, sidebar, CSS, static JS files, error pages
4. **contacts**: contacts blueprint + templates (list, detail, form, modal)
5. **companies**: companies blueprint + templates (list, detail, form)
6. **pipeline**: pipeline blueprint + templates (board, list, detail, form, stats)
7. **projects**: projects blueprint + templates (list, detail, form, templates)
8. **tasks**: tasks blueprint + templates (list, my-day, form, modal)
9. **time-tracking**: time blueprint + templates (entries, timesheet, timer JS)
10. **revenue**: revenue blueprint + templates (income list/form, expense list/form, P&L, reports)
11. **goals**: goals blueprint + templates (targets, history)
12. **notes**: notes blueprint + templates (journal, notes list, form, search)
13. **reports**: reports blueprint + templates (6 report pages, CSV export)
14. **search**: search blueprint + templates (search results, JS dropdown)
15. **settings**: settings blueprint + templates (profile, defaults, categories, export)
16. **dashboard**: dashboard blueprint + templates (main dashboard, Chart.js widgets)

## Risk Areas

1. **Cross-module data flows** — deal→project conversion, time→revenue calculations, contact→everything aggregation. These create integration wiring gaps (FC22) if agents don't wire their components into shared pages.
2. **Endpoint registry scale** — 50+ routes across 16 agents. Any url_for mismatch = BuildError at runtime.
3. **Money conversion consistency** — 8+ modules touch money (pipeline, projects, revenue, expenses, goals, reports, dashboard, settings). All must agree on cents storage + display.
4. **Template render context bloat** — 50+ render_template calls, each with specific kwargs. Mismatched variable names between routes and templates = silent missing data.
5. **Activity log wiring** — dashboard shows "last 10 actions." Every module must INSERT into activity_log. If any module skips it, dashboard has gaps.

## Explicitly Out of Scope

- Email integration or sending
- File uploads / storage
- Calendar sync (Google Calendar, iCal)
- Client portal / client-facing views
- Invoicing (separate Invoice app exists)
- Mobile app or responsive design (desktop-first)
- Team features / multi-user
- API endpoints (JSON)
- Integrations (Stripe, QuickBooks, etc.)
- Drag-and-drop anywhere
- WYSIWYG editor (textarea only)

## Feed-Forward

- **Hardest decision:** Whether to store time as decimal hours or integer minutes. Chose integer minutes for precision (no floating-point rounding), but this means every display site needs a minutes→hours conversion and every input site needs hours→minutes conversion. Two conversion surfaces (like money/cents) — spec must prescribe both.
- **Rejected alternatives:** (1) Tags as junction table — too complex for MVP, comma-separated text with LIKE search is sufficient. (2) React/Vue for interactive features — vanilla JS is simpler and matches sandbox standard. (3) Separate income/expense blueprints — combined into single "revenue" blueprint since they share views (P&L, monthly). (4) SQLAlchemy ORM — raw SQL with sqlite3 is simpler, matches prior builds, avoids ORM complexity.
- **Least confident:** The activity log wiring across 16 agents. Every module that creates/updates/deletes records needs to INSERT into activity_log with a consistent format. If the spec doesn't prescribe the exact INSERT call per module, agents will either skip it or use inconsistent formats. This is FC22 (integration wiring gap) waiting to happen. The spec must include an "Activity Log Insert" section with exact SQL per operation.

## Refinement Findings

**Gaps found:** 5

1. **Transaction Boundary Prescription** — The spec must explicitly assign commit ownership for every multi-step write (deal→project conversion, time→revenue flows, goal actuals updates). Without it, agents default to commit-per-write and break multi-step flows. (Source: workshop-registration-hub, FC29)

2. **Coordinated Behaviors Spec Section** — A mandatory reference table (one row per write operation: flash message text, log_activity required, validation rules) prevents 16 agents from making inconsistent UX decisions. The activity log gap is just one symptom. (Source: project-tracker-5-agent, FC5)

3. **Data Ownership Table for 21 Tables** — Formal `| Table | Writer | Reader(s) |` for all 21 tables prevents double-write conflicts. Dashboard, revenue, and reports agents all read aggregated data; without ownership, at least one will also write it. (Source: chain-reaction-contracts)

4. **Context Manager and Scalar Return Usage Examples** — `with get_db() as db:` and `project_id = create_project(...)` must appear as code examples in the spec, not just type signatures. Both mistakes occurred in prior 4-agent builds; 16 agents makes repetition near-certain. (Source: flask-swarm-acid-test, task-tracker-categories, FC2)

5. **Route Decorator Paths Must Be Relative** — Spec must explicitly state `@bp.route()` paths are relative to `url_prefix`. Confirmed swarm-specific bug that silently breaks entire blueprints. (Source: personal-finance-tracker, FC7)

STATUS: PASS
