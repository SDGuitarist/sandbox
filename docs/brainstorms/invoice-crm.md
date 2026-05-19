---
title: Invoice & CRM Application Brainstorm
date: 2026-05-19
status: complete
type: brainstorm
project: invoice-crm
feed_forward:
  risk: "15+ agent swarm at scale -- spec size (~1200 lines) and cross-blueprint data flows (deal-to-invoice, payment-to-invoice-status) are the highest coordination risk"
  verify_first: true
---

# Invoice & CRM Application -- Brainstorm

## App Brief

**Name:** InvoiceCRM
**Target user:** Single user -- freelancers, agencies, small businesses who need to track clients, send invoices, and manage their sales pipeline in one place
**Tech stack:** Flask + SQLite + Jinja2 (sandbox standard)
- flask-wtf for CSRF on all POST forms
- Bootstrap 5 via CDN for professional UI
- Chart.js via CDN for dashboard charts (optional -- tables acceptable)
- Vanilla JS only where needed (search, pipeline stage buttons)
- bcrypt for password hashing
**Monetization:** Freshbooks/Wave competitor for solo operators -- $29-79/mo SaaS. Revenue reports + aging reports are the features people pay for.

## Core Features (MVP)

1. **Auth + Business Profile:** Register/login with bcrypt, user profile with business info (company name, logo URL, address, phone, email, tax ID). Business info auto-populates on invoices.
2. **CRM -- Client Management:** Client records (name, email, phone, company, address, notes, tags), list with search/filter/sort, detail page with all invoices/payments/interactions, activity log (manual entry), client status (active/inactive/lead).
3. **CRM -- Sales Pipeline:** Deals with title/client/value/stage/expected close date/notes. Stages: Lead > Qualified > Proposal > Negotiation > Won > Lost. Pipeline dashboard with value per stage. Button-based stage transitions (no drag-and-drop). Deal-to-invoice flow when marked "Won."
4. **Product/Service Catalog:** Reusable line items (name, description, unit price, unit type). CRUD. Pull into invoices via dropdown.
5. **Invoice Management:** Create with client + line items (catalog or custom), quantity, per-line tax rate. Auto-calculated subtotal/tax/total. Auto-increment numbering (INV-001), configurable prefix. Status workflow: Draft > Sent > Viewed > Paid > Overdue. Due date with overdue detection on page load. Detail page, duplicate invoice, list with filters.
6. **Recurring Invoices:** Mark invoice as recurring (weekly/monthly/quarterly/annually). Auto-generate next invoice on dashboard load. Track recurrence history (parent > children).
7. **Payments:** Record payment against invoice (amount, date, method). Partial payments -- invoice stays open until fully paid. Payment history per invoice and per client. Overpayment flagging.
8. **Dashboard:** Revenue summary (this month, last month, YTD, outstanding, overdue), recent invoices (10), overdue alerts, pipeline value summary, upcoming recurring invoices (7 days), top 5 clients by revenue.
9. **Reports:** Revenue by month (table), revenue by client (ranked), aging report (0-30, 31-60, 61-90, 90+ days), pipeline forecast (expected revenue by month from deal close dates x probability), CSV export.
10. **Settings:** Business profile, invoice defaults (payment terms, default tax rate, prefix), currency display setting.
11. **Global Search:** Search bar in nav -- searches clients, invoices (by number), deals (by title). Results grouped by type with links.

## Explicitly Out of Scope

- Email sending (just track "marked as sent")
- Online payment processing (Stripe, Square, etc.)
- Multi-user / team features
- API endpoints (web UI only)
- PDF generation (v2)
- Multi-currency
- Inventory management
- Drag-and-drop UI

## Technical Decisions

### Database Schema Design

**Money storage:** Integer cents in DB, divide by 100 for display. Jinja2 `|dollars` filter for templates, manual `'%.2f' % (amount / 100)` for form prefill. This avoids floating-point rounding issues on invoice totals. (Lesson from: personal-finance-tracker)

**Schema overview (13 tables):**
- `users` -- id, email, password_hash, company_name, logo_url, address, phone, tax_id, invoice_prefix, default_payment_terms, default_tax_rate, currency, created_at
- `clients` -- id, user_id, name, email, phone, company, address, notes, status (active/inactive/lead), created_at, updated_at
- `client_tags` -- id, user_id, name (unique per user)
- `client_tag_map` -- client_id, tag_id (composite PK)
- `activities` -- id, client_id, user_id, type (call/email/meeting), notes, activity_date, created_at
- `deals` -- id, user_id, client_id (FK), title, value_cents, stage, expected_close_date, probability, notes, created_at, updated_at
- `catalog_items` -- id, user_id, name, description, unit_price_cents, unit (hour/item/project/month), created_at
- `invoices` -- id, user_id, client_id (FK), invoice_number, status (draft/sent/viewed/paid/overdue), issue_date, due_date, subtotal_cents, tax_cents, total_cents, notes, is_recurring, recurrence_interval, parent_invoice_id, created_at, updated_at
- `invoice_line_items` -- id, invoice_id (FK), catalog_item_id (FK nullable), description, quantity, unit_price_cents, tax_rate, line_total_cents
- `payments` -- id, invoice_id (FK), amount_cents, payment_date, method (cash/check/bank_transfer/card/other), notes, created_at
- `settings` -- user_id (PK), invoice_prefix, default_payment_terms, default_tax_rate, currency, updated_at

Wait -- settings can just be columns on the `users` table. Simpler. Let me merge them.

Revised: 12 tables. Settings stored as user columns.

**Foreign keys:** All FKs use ON DELETE CASCADE for client-owned data (when client deleted, their invoices/activities/deals go too). PRAGMA foreign_keys=ON per connection.

**Indexes:** On client_id for invoices, payments, activities, deals. On status for invoices (overdue queries). On invoice_id for line_items and payments.

### Application Architecture

**Flask blueprint structure (one blueprint per feature domain):**
- `auth` -- /auth/register, /auth/login, /auth/logout, /auth/profile
- `clients` -- /clients/, /clients/<id>, /clients/new, /clients/<id>/edit, /clients/<id>/delete
- `activities` -- /clients/<client_id>/activities/new (nested under clients)
- `pipeline` -- /pipeline/, /pipeline/new, /pipeline/<id>, /pipeline/<id>/edit, /pipeline/<id>/move
- `catalog` -- /catalog/, /catalog/new, /catalog/<id>/edit, /catalog/<id>/delete
- `invoices` -- /invoices/, /invoices/new, /invoices/<id>, /invoices/<id>/edit, /invoices/<id>/status, /invoices/<id>/duplicate
- `recurring` -- /invoices/<id>/recurring (set recurrence), auto-generation logic called from dashboard
- `payments` -- /invoices/<id>/payments/new, /payments/ (all payments list)
- `dashboard` -- / (root)
- `reports` -- /reports/, /reports/revenue, /reports/aging, /reports/forecast, /reports/export
- `settings` -- /settings/
- `search` -- /search?q=...

**Blueprint-scoped templates:** Each blueprint has its own `templates/<blueprint_name>/` directory. Base template at `app/templates/base.html`.

**Shared modules:**
- `db.py` -- `get_db()` context manager (yields connection, caller commits), `init_db()` with all CREATE TABLE IF NOT EXISTS
- `helpers.py` -- Jinja2 filters (`dollars`, `format_date`), flash message helpers, login_required decorator

### Transaction Boundary Policy

Functions that modify data do NOT commit -- caller controls transaction. This prevents the FC29 pattern (premature commit breaking multi-step flows like deal-to-invoice).

Example: `create_invoice_from_deal(db, deal_id)` creates the invoice and line items but does NOT commit. The route handler commits after all steps succeed.

### Invoice Numbering

Auto-increment based on MAX(invoice_number) + 1 for the user. Prefix from user settings (default "INV"). Format: `{prefix}-{number:03d}`. Atomic: SELECT MAX + INSERT in same transaction to prevent duplicates.

### Overdue Detection

On dashboard load and invoice list load: UPDATE invoices SET status='overdue' WHERE status='sent' AND due_date < date('now'). Simple, no background jobs.

### Recurring Invoice Generation

On dashboard load: check for invoices where is_recurring=1 AND next recurrence date <= today. Generate new draft invoice copying line items from parent. Set parent's next_recurrence_date forward. Track parent_invoice_id on children.

### Deal-to-Invoice Flow

When deal stage changes to "Won": redirect to invoice creation form pre-populated with deal's client and value. User can adjust line items before saving.

### Search Implementation

Simple LIKE queries across clients.name, invoices.invoice_number, deals.title. No full-text search needed for MVP. Results grouped by type in template.

## Swarm Agent Strategy (15 agents)

Vertical split by blueprint -- each agent owns one blueprint package with routes, forms, and templates. No cross-agent imports except shared modules (db.py, helpers.py).

| # | Agent Role | Owns |
|---|-----------|------|
| 1 | scaffold | app factory, config, db.py, helpers.py, base template, run.py, requirements.txt |
| 2 | auth | auth blueprint + templates |
| 3 | clients | clients blueprint + templates |
| 4 | activities | activities blueprint + templates |
| 5 | pipeline | pipeline/deals blueprint + templates |
| 6 | catalog | catalog blueprint + templates |
| 7 | invoices | invoices blueprint + templates |
| 8 | recurring | recurring invoice logic + templates |
| 9 | payments | payments blueprint + templates |
| 10 | dashboard | dashboard blueprint + templates |
| 11 | reports | reports blueprint + templates |
| 12 | settings | settings blueprint + templates |
| 13 | search | search blueprint + templates |
| 14 | static | CSS overrides, vanilla JS (search autocomplete, pipeline buttons) |
| 15 | tests | pytest test files for all blueprints |

**Critical coordination points:**
- Scaffold agent defines ALL models (CREATE TABLE statements) -- other agents only READ schema, never modify it
- Endpoint registry table maps every route to its url_for name -- templates agent and cross-linking agents use ONLY these names
- All money values stored as integer cents -- every agent uses `helpers.dollars` filter for display
- Transaction boundaries: route handlers commit, helper functions do not

## Lessons Applied from Prior Builds

1. **CSRF on all POST forms** (autopilot-swarm-orchestration, bookmark-manager) -- flask-wtf CSRFProtect in app factory, {{ form.hidden_tag() }} in every form
2. **SECRET_KEY from environment** (autopilot-swarm-orchestration) -- `os.environ.get('SECRET_KEY', secrets.token_hex(24))`
3. **Endpoint registry table** (bookmark-manager, memory endpoint_registry.md) -- every Flask route needs Blueprint | Function | Method | Path | url_for Name
4. **Route prefix relative to blueprint** (personal-finance-tracker, FC7) -- decorators are RELATIVE to prefix
5. **Cents storage** (personal-finance-tracker) -- integer cents in DB, |dollars Jinja2 filter
6. **Transaction boundaries prescribed** (workshop-registration-hub, FC29) -- functions do NOT commit
7. **Parallel array zip() safety** (recipe-organizer) -- length check before zip() on invoice line items
8. **Context manager usage examples** (flask-swarm-acid-test) -- spec shows `with get_db() as db:` not just signature
9. **WAL mode persistent, foreign_keys per-connection** (recipe-organizer, personal-finance-tracker) -- PRAGMA journal_mode=WAL in init_db(), PRAGMA foreign_keys=ON in get_db()
10. **Batch fetch for N+1** (bookmark-manager) -- batch query pattern for client tags, invoice counts
11. **Idempotent DDL** (FC16) -- CREATE TABLE IF NOT EXISTS everywhere
12. **Pre-swarm spec consistency gate** (spec-convergence-loop) -- catches cross-section contradictions
13. **Prescriptive code blocks for integration files** (flask-swarm-acid-test) -- app factory gets exact code, not description
14. **No cross-agent imports** (flask-swarm-acid-test) -- all imports point to shared modules

## Risks and Open Questions

1. **Spec size:** At ~1200 lines, this is the largest spec we've attempted. Risk of cross-section contradictions increases with size. Mitigation: spec-consistency-checker + thorough endpoint registry.
2. **Deal-to-invoice flow:** Crosses pipeline and invoices blueprints. Need clear contract: pipeline routes redirect to `/invoices/new?from_deal=<id>`, invoices routes handle the prefill.
3. **Recurring invoice generation:** Runs on dashboard load -- could be slow with many recurring invoices. Mitigation: limit to invoices due within 7 days, batch generate.
4. **Invoice total calculation:** Subtotal, tax, and total are stored AND calculated. Risk of stale stored values if line items change. Mitigation: recalculate on every save.
5. **15 agents = 15 merge points.** Prior max was 8 agents. Expect 2-3 merge conflicts and 5+ review findings above prior builds.

## Feed-Forward

- **Hardest decision:** Agent split granularity -- 15 agents means some are very thin (activities, recurring, static) but keeps ownership boundaries clean. Merging would create shared-file conflicts.
- **Rejected alternatives:** (1) Fewer agents with merged blueprints (clients+activities, invoices+recurring+payments) -- rejected because shared template directories cause merge conflicts in swarm. (2) Monolith single-agent build -- rejected because user explicitly requested 15+ agent swarm. (3) Node/Express stack -- rejected because user specified Flask.
- **Least confident:** The deal-to-invoice cross-blueprint flow and recurring invoice generation on dashboard load. These are the two features that cross ownership boundaries most heavily. The spec must prescribe exact URL parameters and query patterns for both.

## Refinement Findings

**Gaps found:** 5 (all addressed in plan)

1. **Coordinated Behaviors table needed** (from: project-tracker-5-agent-swarm) -- Spec must prescribe which routes across all 15 agents log activities and flash messages, or agents will be inconsistent.
2. **Cross-Boundary Wiring section needed** (from: ethics-toolkit-platform) -- Dead wiring risk on deal-to-invoice and dashboard-calls-recurring. Spec must state who calls what, when, with what params.
3. **Per-agent transaction boundary annotations** (from: workshop-registration-hub, FC29) -- Every function in every blueprint needs explicit "does NOT commit" annotation, not just cross-boundary flows. Affects invoice status transitions, payment recording, recurring generation.
4. **Form prefill as separate money conversion surface** (from: personal-finance-tracker) -- `|dollars` filter handles display but edit forms need manual `'%.2f' % (cents / 100)`. 7+ agents build forms; spec must prescribe the pattern.
5. **Flask 3.0 patterns** (from: feedback-board-solo-build) -- Use `FLASK_DEBUG=1` not `FLASK_ENV`. init_db needs try/finally for FD leak prevention.
