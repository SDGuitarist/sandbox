# Pre-Swarm Spec Consistency Check

**Plan:** `docs/plans/solopreneur-command-center.md`
**Checked:** 2026-05-19

---

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Schema vs Model | `deal.probability_pct` (SQL) | `create_deal(..., probability_pct=10)` (model) | PASS | Exact name match |
| 2 | Schema vs Model | `time_entry.minutes` (SQL) | `create_time_entry(..., minutes=0)` (model) | PASS | Exact name match |
| 3 | Schema vs Model | `task.estimated_hours` (SQL) | `create_task(..., estimated_hours=0)` (model) | PASS | Exact name match |
| 4 | Schema vs Model | `income.payment_method` (SQL) | `create_income(..., payment_method='bank_transfer')` (model) | PASS | Exact name match |
| 5 | Schema vs Model | `expense.tax_deductible` (SQL) | `create_expense(..., tax_deductible=0)` (model) | PASS | Exact name match |
| 6 | Schema vs Model | `project.hourly_rate` (SQL) | `create_project(..., hourly_rate=0)` (model) | PASS | Exact name match |
| 7 | SQL Type vs App-Layer | `task.estimated_hours REAL` (SQL) | `estimated_hours=0` int default (model) | PASS | SQLite coerces; compatible at runtime |
| 8 | SQL Type vs App-Layer | `deal.value INTEGER` cents (SQL) | `value=0` in model; money conversion produces int (Coordinated Behaviors) | PASS | Consistent integer-cents convention throughout |
| 9 | SQL Type vs App-Layer | `goal.revenue_target INTEGER` (SQL) | `revenue_target=revenue_target, # int (cents)` (goals render context) | PASS | Unit explicitly labeled as cents in comment |
| 10 | SQL Type vs App-Layer | `goal.hours_target INTEGER` (SQL) | `hours_target=hours_target, # int` (goals render context comment) | WARN | Unit not labeled. Time tracking uses minutes everywhere else. If agents store hours_target in hours, it cannot be compared directly to time_entry.minutes values. |
| 11 | Route Table vs Template | `revenue.by_client GET /by-client` (endpoint registry line 845) | No template render context defined; no template file in directory structure | FAIL | Route exists in endpoint registry but has zero template coverage in spec. No render context block, no template file in directory structure, not listed in revenue agent file assignment. Revenue agent will have no guidance on what to render. |
| 12 | Route Table vs Template | `revenue.by_month GET /by-month` (endpoint registry line 846) | No template render context defined; no template file in directory structure | FAIL | Same as #11. The variable `by_month` appearing in `pl.html` render context is a data variable, not a template path -- unrelated. Route has no template at all. |
| 13 | Directory Structure vs render_template() | `reports/index.html` absent from directory structure (lines 165-171) | `render_template('reports/index.html')` in render context; included in swarm agent assignment (line 1144); `reports.index GET /` in endpoint registry | FAIL | Directory structure omits this file. Three other sections agree it must exist. Reports agent must create it, but if agents use the directory structure as the canonical file list, the file will be skipped. |
| 14 | Export Name vs Import | `bp = Blueprint('time_tracking', ...)` (__init__.py template) | `time_tracking.index`, `time_tracking.create`, etc. in endpoint registry | PASS | Blueprint name matches all url_for prefixes exactly |
| 15 | Export Name vs Import | `url_for('dashboard.index')` in app factory root redirect | `dashboard.index` in endpoint registry | PASS | Exact match |
| 16 | Export Name vs Import | `url_for('auth.login')` in decorators.py | `auth.login` in endpoint registry | PASS | Exact match |
| 17 | Export Name vs Import | `url_for('auth.setup')` in decorators.py | `auth.setup` in endpoint registry | PASS | Exact match |
| 18 | Blueprint Name vs url_for | 14 blueprints registered in app factory with module-matching names | 14 url_for prefixes in endpoint registry | PASS | auth, contacts, companies, pipeline, projects, tasks, time_tracking, revenue, goals, notes, reports, search, settings, dashboard -- all consistent across registration and registry |
| 19 | Activity Log entity_type vs Table Names | entity_type values prescribed in Coordinated Behaviors: contact, company, deal, project, task, time_entry, income, expense, journal_entry, note, goal, business_profile | Corresponding SQL table names in schema.sql | PASS | All 12 entity_type strings are exact matches of their SQL table names |
| 20 | Pipeline Stage Names vs PIPELINE_STAGES | `deal.stage DEFAULT 'lead'` in schema; `stage='lead'` in create_deal() | PIPELINE_STAGES first entry is `('lead', 'Lead', 10)` | PASS | Default stage value matches PIPELINE_STAGES[0][0] |
| 21 | Pipeline Stage Names vs PIPELINE_STAGES | PIPELINE_STAGES keys: lead, discovery, proposal_sent, negotiation, verbal_yes, won, lost | `deal.stage TEXT` in schema (no CHECK constraint) | PASS | No schema constraint to contradict; stage values are application-enforced via PIPELINE_STAGES |
| 22 | Data Ownership vs Schema FKs | deal owned by pipeline; projects listed as reader of deal | `project.deal_id REFERENCES deal(id)` in schema | PASS | FK supports projects reading deals for won-deal-to-project flow |
| 23 | Data Ownership vs Schema FKs | contact owned by contacts; pipeline listed as reader | `deal.contact_id REFERENCES contact(id)` in schema | PASS | FK supports pipeline reading contacts |
| 24 | Data Ownership vs Schema FKs | project owned by projects; time_tracking listed as reader | `time_entry.project_id REFERENCES project(id)` in schema | PASS | FK supports time_tracking reading projects |
| 25 | Data Ownership vs Schema FKs | task owned by tasks; time_tracking listed as reader | `time_entry.task_id REFERENCES task(id)` in schema | PASS | FK supports time_tracking reading tasks |
| 26 | Data Ownership vs Schema FKs | income owned by revenue; goals listed as reader | `income` has no FK to `goal` table | PASS | Goals reads income by date aggregation (no FK required); ownership table is accurate |
| 27 | Data Ownership vs Schema FKs | milestone owned by projects; dashboard listed as reader | `milestone.project_id REFERENCES project(id)` in schema | PASS | FK supports dashboard reading milestones via project_id |
| 28 | Mock/Fixture vs Schema | Seed: `INSERT OR IGNORE INTO income_category (name, is_default) VALUES ('project_payment', 1), ('retainer', 1), ('consulting', 1), ('product_sale', 1), ('other', 1)` | `income_category(id, name TEXT UNIQUE, is_default INTEGER)` in schema | PASS | All inserted columns exist; name and is_default match schema; id is AUTOINCREMENT so omitting it is correct |
| 29 | Mock/Fixture vs Schema | Seed: `INSERT OR IGNORE INTO expense_category (name, is_default)` with 8 values | `expense_category(id, name TEXT UNIQUE, is_default INTEGER)` in schema | PASS | All inserted columns exist and match schema |
| 30 | Cross-Boundary Wiring | `get_revenue_snapshot(db, user_id)` model function signature | Dashboard render context: `revenue=revenue` with no call-site shown; user_id source not documented | WARN | Dashboard agent must pass `session['user_id']` as the second argument. Spec does not document this at the call site. Agent may call `get_revenue_snapshot(db)` and get TypeError. |
| 31 | Route Table vs Template | `settings.export_module GET /export/<module>` (endpoint registry line 892) | No template render context defined for this route | WARN | Most likely intentional (file download / CSV response). Spec does not explicitly state this. Agent may attempt to render a template that does not exist. |
| 32 | Blueprint Count | "14 blueprints" stated in Flask Best Practices note | Actual registrations in app factory: 14 blueprints | PASS | 16 agents minus core-infra and layout-static (no blueprints) equals 14. Matches the note. |
| 33 | Schema vs Model Enum | `contact.status DEFAULT 'lead'`; app enum `['lead', 'active_client', 'past_client', 'partner']` | `create_contact(..., status='lead')` model default | PASS | Default value is a valid enum member |
| 34 | Schema vs Model Enum | `project.type DEFAULT 'hourly'`; app enum `['fixed_price', 'hourly', 'retainer', 'pro_bono']` | `create_project(..., type='hourly')` model default | PASS | Default value is a valid enum member |
| 35 | Cross-Boundary Wiring | `notes_fts` and `journal_fts` virtual tables in Data Ownership table | FTS5 virtual tables defined in schema.sql with correct content table references | PASS | notes_fts maps to note table; journal_fts maps to journal_entry table; both present in schema |

---

## Summary

- **Total checks:** 35
- **PASS:** 28
- **FAIL:** 3
- **WARN:** 4
- **N/A (section absent):** 0

---

## FAIL Details

### FAIL 1 -- `revenue.by_client` route has no template

**Endpoint registry line 845:** `by_client | GET | /by-client | revenue.by_client`

**Problem:** The Template Render Context section covers only five revenue templates: `income_list.html`, `income_form.html`, `expense_list.html`, `expense_form.html`, `pl.html`. Neither `revenue/by_client.html` nor a render context block for `revenue.by_client` exists anywhere in the spec. The directory structure (lines 148-156) lists the same five files and does not include a by_client template. The swarm agent assignment for the revenue agent lists the same five template files only.

The revenue agent will encounter a route with no template guidance. It will likely either return a blank response, guess a template name, or render an existing template with wrong variables.

**Fix options:**
- Add a `revenue/by_client.html` template file to the directory structure and a render context block to the Template Render Context section. Add the file to the revenue agent's file assignment.
- If this route is a redirect to `reports.client_report`, replace the route body with `return redirect(url_for('reports.client_report'))` and document that in the spec so agents know no template is needed.

---

### FAIL 2 -- `revenue.by_month` route has no template

**Endpoint registry line 846:** `by_month | GET | /by-month | revenue.by_month`

**Problem:** Identical to FAIL 1. No template render context, no template file in directory structure, not in revenue agent file assignment. The name `by_month` appears only as a context variable inside `pl.html` render context -- that is a data variable, not a template path.

**Fix options:**
- Add `revenue/by_month.html` template to spec with render context.
- Or redirect to `revenue.pl` or `reports.revenue_report` and document that explicitly.

---

### FAIL 3 -- `reports/index.html` missing from directory structure

**Directory structure lines 165-171** (under `reports/`):
```
revenue.html
client.html
time.html
pipeline.html
utilization.html
expense.html
```

**Problem:** `reports/index.html` is absent from the directory structure but present in three other sections:
- Endpoint registry: `index | GET | / | reports.index`
- Template Render Context: `render_template('reports/index.html')`
- Swarm agent assignment: `command-center/app/templates/reports/index.html` in reports agent file list

The directory structure is the odd one out. If the reports agent uses the directory structure as its authoritative file list, it will skip creating `reports/index.html`, leaving the `reports.index` route with no template and causing a TemplateNotFound error at runtime.

**Fix:** Add `index.html` as the first entry under the `reports/` section of the directory structure, between lines 165 and 166.

---

## WARN Details

### WARN 1 -- `goal.hours_target` unit is ambiguous

Schema stores `hours_target INTEGER NOT NULL DEFAULT 0`. The goals render context comment says `hours_target=hours_target, # int` with no unit. Every other time-related integer in the spec specifies its unit in the comment (e.g., `total_hours, # int (minutes)`, `billable_hours, # int (minutes)`, `target=target) # int (minutes)`).

If the goals agent stores hours_target in whole hours while the dashboard agent compares it to `get_hours_this_week()` which returns `logged` in minutes, the percentage calculation will be off by a factor of 60.

**Fix:** Change the goals render context comment to `hours_target=hours_target, # int (minutes)` (or `# int (hours)` if intentionally different, with a conversion note for the dashboard agent).

---

### WARN 2 -- `get_revenue_snapshot(db, user_id)` call site undocumented for dashboard agent

The model function signature requires a `user_id` parameter. The dashboard render context shows `revenue=revenue` as the result variable. Neither the render context block nor the model functions section shows the call:

```python
revenue = get_revenue_snapshot(db, session['user_id'])
```

The dashboard agent must infer that `user_id` comes from `session['user_id']`. This is likely but not guaranteed -- an agent that uses `None` or omits the argument will get a TypeError or an empty result.

**Fix:** Add a usage note in the dashboard render context or in the Dashboard Query Functions section showing the full call with `session['user_id']`.

---

### WARN 3 -- `settings.export_module` has no render context and no template

Endpoint registry line 892: `export_module | GET | /export/<module> | settings.export_module`

No Template Render Context block is defined for this route. The settings agent owns only `export.html` (for `export_data`). If the agent treats all GET routes as HTML-returning, it will attempt to render a template that does not exist.

This is most likely intentional -- the route generates a file download (CSV). If so, the spec should say so explicitly so the agent does not guess.

**Fix:** Add a comment to the endpoint registry or Template Render Context section: `# export_module: returns CSV file response (no render_template call)`.

---

### WARN 4 -- `business_profile` revenue targets lack unit labels in render context

`business_profile.monthly_revenue_target INTEGER` and `business_profile.quarterly_revenue_target INTEGER` are stored in the schema. The settings render context passes the entire `profile` Row to `settings/targets.html`. No unit label comment documents whether these are stored in cents (consistent with all other money fields) or whole dollars.

If the settings agent stores them as whole dollars instead of cents, and the goals agent or dashboard agent reads them as cents, targets will appear 100x larger than intended.

**Fix:** Add `# INTEGER (cents)` labels to the `business_profile.monthly_revenue_target` and `business_profile.quarterly_revenue_target` column definitions in the schema comment block, or add a note in the settings render context.

---

STATUS: FAIL -- 3 contradictions found
