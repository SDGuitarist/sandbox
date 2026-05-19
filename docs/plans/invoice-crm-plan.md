---
title: Invoice & CRM Application Plan
date: 2026-05-19
status: ready
type: plan
project: invoice-crm
swarm: true
agents: 15
brainstorm: docs/brainstorms/invoice-crm.md
feed_forward:
  risk: "15+ agent swarm at scale -- cross-blueprint data flows (deal-to-invoice, payment-to-invoice-status, recurring generation from dashboard) and spec size (~1200 lines) are highest coordination risk"
  verify_first: true
---

# Invoice & CRM Application -- Plan

## What Exactly Is Changing?

Building a complete Invoice & CRM web application from scratch in `invoice-crm/` subdirectory. Flask + SQLite + Jinja2. 15 swarm agents each own one vertical slice (blueprint + templates). Features: auth, client management, activity logs, sales pipeline, product catalog, invoicing with line items, recurring invoices, payments, dashboard, reports, settings, global search.

## What Must Not Change?

- No files outside `invoice-crm/` (except BUILD_TRACKING.md at sandbox root)
- No modifications to existing sandbox projects
- No production database access
- No external API calls

## How Will We Know It Worked?

See Acceptance Tests section below.

## What Is the Most Likely Way This Plan Is Wrong?

The deal-to-invoice flow and recurring-invoice-from-dashboard flow cross ownership boundaries. If the spec's Cross-Boundary Wiring section has even one ambiguous parameter, the receiving agent will implement it wrong and the flow will be dead at runtime. Secondary risk: 15 agents generating 15 schema-dependent modules means any schema typo in the spec propagates to all agents.

---

## Project Structure

```
invoice-crm/
  run.py                          # Entry point
  requirements.txt                # Dependencies
  .gitignore                      # Python + SQLite ignores
  app/
    __init__.py                   # App factory + blueprint registration
    config.py                     # Configuration class
    db.py                         # get_db() context manager + init_db()
    helpers.py                    # Jinja2 filters, login_required, flash helpers
    templates/
      base.html                   # Base layout with Bootstrap 5 + nav
    static/
      css/style.css               # Custom CSS overrides
      js/app.js                   # Vanilla JS (search, pipeline buttons)
    auth/
      __init__.py                 # Blueprint definition
      routes.py                   # Auth routes
      forms.py                    # WTForms classes
      templates/auth/
        login.html
        register.html
        profile.html
    clients/
      __init__.py
      routes.py
      forms.py
      templates/clients/
        list.html
        detail.html
        form.html
    activities/
      __init__.py
      routes.py
      forms.py
      templates/activities/
        form.html
        list.html
    pipeline/
      __init__.py
      routes.py
      forms.py
      templates/pipeline/
        list.html
        detail.html
        form.html
        kanban.html
    catalog/
      __init__.py
      routes.py
      forms.py
      templates/catalog/
        list.html
        form.html
    invoices/
      __init__.py
      routes.py
      forms.py
      templates/invoices/
        list.html
        detail.html
        form.html
        line_items_partial.html
    recurring/
      __init__.py
      routes.py
      templates/recurring/
        settings.html
        history.html
    payments/
      __init__.py
      routes.py
      forms.py
      templates/payments/
        form.html
        list.html
    dashboard/
      __init__.py
      routes.py
      templates/dashboard/
        index.html
    reports/
      __init__.py
      routes.py
      templates/reports/
        index.html
        revenue_by_month.html
        revenue_by_client.html
        aging.html
        forecast.html
    settings_bp/
      __init__.py
      routes.py
      forms.py
      templates/settings_bp/
        index.html
    search/
      __init__.py
      routes.py
      templates/search/
        results.html
```

---

## Shared Interface Spec

### Database Schema (ALL tables -- scaffold agent creates these in db.py init_db)

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    company_name TEXT DEFAULT '',
    logo_url TEXT DEFAULT '',
    address TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    business_email TEXT DEFAULT '',
    tax_id TEXT DEFAULT '',
    invoice_prefix TEXT DEFAULT 'INV',
    default_payment_terms INTEGER DEFAULT 30,
    default_tax_rate REAL DEFAULT 0.0,
    currency TEXT DEFAULT 'USD',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    address TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive', 'lead')),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_clients_user_id ON clients(user_id);
CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status);

CREATE TABLE IF NOT EXISTS client_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS client_tag_map (
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES client_tags(id) ON DELETE CASCADE,
    PRIMARY KEY (client_id, tag_id)
);

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK(type IN ('call', 'email', 'meeting', 'note')),
    notes TEXT DEFAULT '',
    activity_date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_activities_client_id ON activities(client_id);

CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    value_cents INTEGER DEFAULT 0,
    stage TEXT DEFAULT 'lead' CHECK(stage IN ('lead', 'qualified', 'proposal', 'negotiation', 'won', 'lost')),
    expected_close_date TEXT,
    probability INTEGER DEFAULT 50,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_deals_user_id ON deals(user_id);
CREATE INDEX IF NOT EXISTS idx_deals_client_id ON deals(client_id);
CREATE INDEX IF NOT EXISTS idx_deals_stage ON deals(stage);

CREATE TABLE IF NOT EXISTS catalog_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    unit_price_cents INTEGER DEFAULT 0,
    unit TEXT DEFAULT 'hour' CHECK(unit IN ('hour', 'item', 'project', 'month')),
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_catalog_items_user_id ON catalog_items(user_id);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    invoice_number TEXT NOT NULL,
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft', 'sent', 'viewed', 'paid', 'overdue')),
    issue_date TEXT DEFAULT (date('now')),
    due_date TEXT,
    subtotal_cents INTEGER DEFAULT 0,
    tax_cents INTEGER DEFAULT 0,
    total_cents INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    is_recurring INTEGER DEFAULT 0,
    recurrence_interval TEXT CHECK(recurrence_interval IN ('weekly', 'monthly', 'quarterly', 'annually') OR recurrence_interval IS NULL),
    next_recurrence_date TEXT,
    parent_invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, invoice_number)
);
CREATE INDEX IF NOT EXISTS idx_invoices_user_id ON invoices(user_id);
CREATE INDEX IF NOT EXISTS idx_invoices_client_id ON invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_parent ON invoices(parent_invoice_id);

CREATE TABLE IF NOT EXISTS invoice_line_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    catalog_item_id INTEGER REFERENCES catalog_items(id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    quantity REAL DEFAULT 1.0,
    unit_price_cents INTEGER DEFAULT 0,
    tax_rate REAL DEFAULT 0.0,
    line_total_cents INTEGER DEFAULT 0,
    sort_order INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_line_items_invoice_id ON invoice_line_items(invoice_id);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount_cents INTEGER NOT NULL,
    payment_date TEXT NOT NULL,
    method TEXT DEFAULT 'other' CHECK(method IN ('cash', 'check', 'bank_transfer', 'card', 'other')),
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
```

### Money Convention (ALL agents MUST follow)

- **Storage:** Integer cents in database. `value_cents`, `unit_price_cents`, `amount_cents`, `total_cents`, etc.
- **Display in templates:** Use `{{ value | dollars }}` Jinja2 filter (defined in helpers.py)
- **Form prefill in edit forms:** Use `'%.2f' % (row['column_cents'] / 100)` -- NOT the |dollars filter
- **Form submission:** Convert input to cents: `int(round(float(request.form['amount']) * 100))`
- **Line item total calculation:** `line_total_cents = int(round(quantity * unit_price_cents * (1 + tax_rate / 100)))`
- **Invoice total calculation:** `subtotal_cents = SUM(line_total_cents before tax)`, `tax_cents = SUM(per-line tax)`, `total_cents = subtotal_cents + tax_cents`

### Transaction Boundary Policy (ALL agents MUST follow)

**Rule:** Functions that modify data do NOT call `db.commit()`. The route handler commits after all operations succeed.

```python
# CORRECT -- route handler commits
@bp.route('/invoice/<int:invoice_id>/new', methods=['POST'])
@login_required
def create_payment(invoice_id):
    with get_db() as db:
        insert_payment(db, invoice_id, ...)    # does NOT commit
        recalculate_invoice_totals(db, invoice_id)  # does NOT commit
        db.commit()

# WRONG -- helper function commits
def insert_payment(db, invoice_id, ...):
    db.execute("INSERT INTO payments ...", ...)
    db.commit()  # NEVER do this
```

### get_db() Context Manager (scaffold agent implements)

```python
import sqlite3
from contextlib import contextmanager
from flask import g, current_app

@contextmanager
def get_db():
    """Yield a database connection. Caller must commit. Rolls back on exception."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            timeout=10
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    try:
        yield g.db
    except Exception:
        g.db.rollback()
        raise

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
```

**Usage (ALL agents must use this exact pattern):**
```python
with get_db() as db:
    rows = db.execute("SELECT * FROM clients WHERE user_id = ?", (user_id,)).fetchall()
    # ... do work ...
    db.commit()  # only in route handlers, after all modifications
```

### login_required Decorator (scaffold agent implements in helpers.py)

```python
from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
```

**Usage:** Every route except auth.login, auth.register must be decorated with `@login_required`.

### Jinja2 Filters (scaffold agent implements in helpers.py)

```python
def dollars(cents):
    """Convert cents to dollar display: 15099 -> '$150.99'"""
    if cents is None:
        return '$0.00'
    return f'${cents / 100:,.2f}'

def format_date(date_str):
    """Format ISO date string: '2026-05-19' -> 'May 19, 2026'"""
    if not date_str:
        return ''
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
        return dt.strftime('%b %d, %Y')
    except (ValueError, TypeError):
        return date_str

def register_filters(app):
    app.jinja_env.filters['dollars'] = dollars
    app.jinja_env.filters['format_date'] = format_date
```

### App Factory (scaffold agent implements in app/__init__.py)

```python
import os
import secrets
from flask import Flask
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(24))
    app.config['DATABASE'] = os.path.join(app.instance_path, 'invoicecrm.db')

    os.makedirs(app.instance_path, exist_ok=True)

    csrf.init_app(app)

    from .db import close_db, init_db
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

    from .helpers import register_filters
    register_filters(app)

    # Register ALL blueprints
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .clients import bp as clients_bp
    app.register_blueprint(clients_bp, url_prefix='/clients')

    from .activities import bp as activities_bp
    app.register_blueprint(activities_bp, url_prefix='/clients')

    from .pipeline import bp as pipeline_bp
    app.register_blueprint(pipeline_bp, url_prefix='/pipeline')

    from .catalog import bp as catalog_bp
    app.register_blueprint(catalog_bp, url_prefix='/catalog')

    from .invoices import bp as invoices_bp
    app.register_blueprint(invoices_bp, url_prefix='/invoices')

    from .recurring import bp as recurring_bp
    app.register_blueprint(recurring_bp, url_prefix='/recurring')

    from .payments import bp as payments_bp
    app.register_blueprint(payments_bp, url_prefix='/payments')

    from .dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/')

    from .reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')

    from .settings_bp import bp as settings_bp
    app.register_blueprint(settings_bp, url_prefix='/settings')

    from .search import bp as search_bp
    app.register_blueprint(search_bp, url_prefix='/search')

    return app
```

### Blueprint Template (ALL blueprint agents use this pattern)

```python
# app/<blueprint_name>/__init__.py
from flask import Blueprint

bp = Blueprint('<blueprint_name>', __name__, template_folder='templates')

from . import routes  # noqa: E402, F401
```

Route decorators are RELATIVE to the blueprint prefix. If prefix is `/clients`, the index route is `@bp.route('/')`, NOT `@bp.route('/clients/')`.

### Base Template (scaffold agent creates at app/templates/base.html)

Must include:
- Bootstrap 5 CDN (CSS + JS bundle)
- Chart.js CDN
- Navigation bar with: Dashboard, Clients, Pipeline, Invoices, Catalog, Reports, Settings, Search bar, Logout
- Flash message display block
- `{% block content %}{% endblock %}` for page content
- `{% block scripts %}{% endblock %}` for page-specific JS
- CSRF meta tag for AJAX: `<meta name="csrf-token" content="{{ csrf_token() }}">`

### Navigation Links (ALL template agents use these url_for names)

```html
<a href="{{ url_for('dashboard.index') }}">Dashboard</a>
<a href="{{ url_for('clients.list_clients') }}">Clients</a>
<a href="{{ url_for('pipeline.list_deals') }}">Pipeline</a>
<a href="{{ url_for('invoices.list_invoices') }}">Invoices</a>
<a href="{{ url_for('catalog.list_items') }}">Catalog</a>
<a href="{{ url_for('reports.index') }}">Reports</a>
<a href="{{ url_for('settings_bp.index') }}">Settings</a>
<a href="{{ url_for('auth.logout') }}">Logout</a>
<!-- Search form -->
<form action="{{ url_for('search.search') }}" method="GET">
    <input name="q" placeholder="Search..." value="{{ request.args.get('q', '') }}">
</form>
```

---

## Endpoint Registry

### auth Blueprint (prefix: /auth)

| Function Name | Method | Path | url_for Name | Description |
|---------------|--------|------|-------------|-------------|
| login | GET, POST | /login | auth.login | Login form + handler |
| register | GET, POST | /register | auth.register | Registration form + handler |
| logout | GET | /logout | auth.logout | Clear session, redirect to login |
| profile | GET, POST | /profile | auth.profile | View/edit business profile |

### clients Blueprint (prefix: /clients)

| Function Name | Method | Path | url_for Name | Description |
|---------------|--------|------|-------------|-------------|
| list_clients | GET | / | clients.list_clients | Client list with search/filter/sort |
| create_client | GET, POST | /new | clients.create_client | New client form + handler |
| view_client | GET | /\<int:client_id\> | clients.view_client | Client detail with invoices/payments/activities |
| edit_client | GET, POST | /\<int:client_id\>/edit | clients.edit_client | Edit client form + handler |
| delete_client | POST | /\<int:client_id\>/delete | clients.delete_client | Delete client |

### activities Blueprint (prefix: /clients -- shares prefix with clients)

| Function Name | Method | Path | url_for Name | Description |
|---------------|--------|------|-------------|-------------|
| list_activities | GET | /\<int:client_id\>/activities | activities.list_activities | Activity list for client |
| create_activity | GET, POST | /\<int:client_id\>/activities/new | activities.create_activity | New activity form + handler |
| delete_activity | POST | /\<int:client_id\>/activities/\<int:activity_id\>/delete | activities.delete_activity | Delete activity |

### pipeline Blueprint (prefix: /pipeline)

| Function Name | Method | Path | url_for Name | Description |
|---------------|--------|------|-------------|-------------|
| list_deals | GET | / | pipeline.list_deals | Pipeline kanban view |
| create_deal | GET, POST | /new | pipeline.create_deal | New deal form + handler |
| view_deal | GET | /\<int:deal_id\> | pipeline.view_deal | Deal detail page |
| edit_deal | GET, POST | /\<int:deal_id\>/edit | pipeline.edit_deal | Edit deal form + handler |
| move_deal | POST | /\<int:deal_id\>/move | pipeline.move_deal | Change deal stage |
| delete_deal | POST | /\<int:deal_id\>/delete | pipeline.delete_deal | Delete deal |

### catalog Blueprint (prefix: /catalog)

| Function Name | Method | Path | url_for Name | Description |
|---------------|--------|------|-------------|-------------|
| list_items | GET | / | catalog.list_items | Catalog item list |
| create_item | GET, POST | /new | catalog.create_item | New item form + handler |
| edit_item | GET, POST | /\<int:item_id\>/edit | catalog.edit_item | Edit item form + handler |
| delete_item | POST | /\<int:item_id\>/delete | catalog.delete_item | Delete item |

### invoices Blueprint (prefix: /invoices)

| Function Name | Method | Path | url_for Name | Description |
|---------------|--------|------|-------------|-------------|
| list_invoices | GET | / | invoices.list_invoices | Invoice list with filters |
| create_invoice | GET, POST | /new | invoices.create_invoice | New invoice form + handler |
| view_invoice | GET | /\<int:invoice_id\> | invoices.view_invoice | Invoice detail with line items |
| edit_invoice | GET, POST | /\<int:invoice_id\>/edit | invoices.edit_invoice | Edit invoice form + handler |
| update_status | POST | /\<int:invoice_id\>/status | invoices.update_status | Change invoice status |
| duplicate_invoice | POST | /\<int:invoice_id\>/duplicate | invoices.duplicate_invoice | Copy to new draft |
| delete_invoice | POST | /\<int:invoice_id\>/delete | invoices.delete_invoice | Delete invoice |

### recurring Blueprint (prefix: /recurring)

| Function Name | Method | Path | url_for Name | Description |
|---------------|--------|------|-------------|-------------|
| set_recurring | GET, POST | /\<int:invoice_id\>/settings | recurring.set_recurring | Set/update recurrence settings |
| view_history | GET | /\<int:invoice_id\>/history | recurring.view_history | View generated child invoices |
| generate_recurring | POST | /generate | recurring.generate_recurring | Trigger recurring invoice generation |

### payments Blueprint (prefix: /payments)

| Function Name | Method | Path | url_for Name | Description |
|---------------|--------|------|-------------|-------------|
| create_payment | GET, POST | /invoice/\<int:invoice_id\>/new | payments.create_payment | Record payment form + handler |
| list_payments | GET | / | payments.list_payments | All payments list |
| delete_payment | POST | /\<int:payment_id\>/delete | payments.delete_payment | Delete a payment |

### dashboard Blueprint (prefix: /)

| Function Name | Method | Path | url_for Name | Description |
|---------------|--------|------|-------------|-------------|
| index | GET | / | dashboard.index | Main dashboard |

### reports Blueprint (prefix: /reports)

| Function Name | Method | Path | url_for Name | Description |
|---------------|--------|------|-------------|-------------|
| index | GET | / | reports.index | Reports overview |
| revenue_by_month | GET | /revenue-by-month | reports.revenue_by_month | Monthly revenue table |
| revenue_by_client | GET | /revenue-by-client | reports.revenue_by_client | Client revenue ranking |
| aging | GET | /aging | reports.aging | Aging report |
| forecast | GET | /forecast | reports.forecast | Pipeline forecast |
| export_csv | GET | /export/\<report_type\> | reports.export_csv | CSV export |

### settings_bp Blueprint (prefix: /settings)

| Function Name | Method | Path | url_for Name | Description |
|---------------|--------|------|-------------|-------------|
| index | GET, POST | / | settings_bp.index | Settings form + handler |

### search Blueprint (prefix: /search)

| Function Name | Method | Path | url_for Name | Description |
|---------------|--------|------|-------------|-------------|
| search | GET | / | search.search | Global search results |

---

## Cross-Boundary Wiring Table

These are flows where one blueprint's route redirects to or calls logic from another blueprint. Each entry specifies EXACTLY what happens at the boundary.

### Deal Won -> Create Invoice

**Trigger:** pipeline agent's `move_deal` route, when `new_stage == 'won'`
**Action:** Redirect to `url_for('invoices.create_invoice', from_deal=deal_id)`
**Receiver:** invoices agent's `create_invoice` GET handler checks `request.args.get('from_deal')`:
- If present: load deal by ID, prefill client_id from deal.client_id, prefill notes with deal title
- User adds line items manually (deal value is informational, not auto-split into line items)

```python
# In pipeline/routes.py move_deal:
if new_stage == 'won':
    flash(f'Deal "{deal["title"]}" marked as Won! Create an invoice?', 'success')
    return redirect(url_for('invoices.create_invoice', from_deal=deal_id))

# In invoices/routes.py create_invoice GET:
from_deal_id = request.args.get('from_deal', type=int)
prefill_client_id = None
prefill_notes = ''
if from_deal_id:
    with get_db() as db:
        deal = db.execute("SELECT * FROM deals WHERE id = ? AND user_id = ?",
                          (from_deal_id, session['user_id'])).fetchone()
        if deal:
            prefill_client_id = deal['client_id']
            prefill_notes = f"From deal: {deal['title']}"
```

### Dashboard -> Recurring Invoice Generation

**Trigger:** dashboard agent's `index` route, on every GET request
**Action:** Call recurring generation logic directly (NOT via HTTP redirect)
**Implementation:** The recurring agent provides a function `generate_due_invoices(db, user_id)` in `app/recurring/routes.py` that the dashboard agent imports.

```python
# In app/recurring/routes.py (recurring agent creates this function):
def generate_due_invoices(db, user_id):
    """Generate invoices for recurring items due today or earlier.
    Does NOT commit -- caller commits.
    Returns count of invoices generated."""
    due = db.execute("""
        SELECT * FROM invoices
        WHERE user_id = ? AND is_recurring = 1
          AND next_recurrence_date IS NOT NULL
          AND next_recurrence_date <= date('now')
          AND status != 'draft'
    """, (user_id,)).fetchall()

    count = 0
    for inv in due:
        # Generate next invoice number
        max_num = db.execute(
            "SELECT MAX(CAST(SUBSTR(invoice_number, LENGTH(?) + 2) AS INTEGER)) FROM invoices WHERE user_id = ?",
            (inv['invoice_number'][:3], user_id)
        ).fetchone()[0] or 0
        user_row = db.execute("SELECT invoice_prefix, default_payment_terms FROM users WHERE id = ?", (user_id,)).fetchone()
        prefix = user_row['invoice_prefix']
        payment_terms = user_row['default_payment_terms']
        new_number = f"{prefix}-{max_num + 1:03d}"

        # Copy invoice
        db.execute("""
            INSERT INTO invoices (user_id, client_id, invoice_number, status, issue_date, due_date,
                                  subtotal_cents, tax_cents, total_cents, notes, parent_invoice_id)
            VALUES (?, ?, ?, 'draft', date('now'), date('now', '+' || ? || ' days'), ?, ?, ?, ?, ?)
        """, (user_id, inv['client_id'], new_number,
              payment_terms,
              inv['subtotal_cents'], inv['tax_cents'], inv['total_cents'],
              inv['notes'], inv['id']))
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Copy line items
        items = db.execute("SELECT * FROM invoice_line_items WHERE invoice_id = ?", (inv['id'],)).fetchall()
        for item in items:
            db.execute("""
                INSERT INTO invoice_line_items (invoice_id, catalog_item_id, description, quantity,
                                                unit_price_cents, tax_rate, line_total_cents, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (new_id, item['catalog_item_id'], item['description'], item['quantity'],
                  item['unit_price_cents'], item['tax_rate'], item['line_total_cents'], item['sort_order']))

        # Advance recurrence date
        interval_map = {'weekly': '+7 days', 'monthly': '+1 month', 'quarterly': '+3 months', 'annually': '+1 year'}
        modifier = interval_map.get(inv['recurrence_interval'], '+1 month')
        db.execute("""
            UPDATE invoices SET next_recurrence_date = date(next_recurrence_date, ?)
            WHERE id = ?
        """, (modifier, inv['id']))
        count += 1

    return count

# In app/dashboard/routes.py (dashboard agent imports and calls):
from app.recurring.routes import generate_due_invoices

@bp.route('/')
@login_required
def index():
    with get_db() as db:
        user_id = session['user_id']
        generated = generate_due_invoices(db, user_id)
        if generated > 0:
            db.commit()
            flash(f'{generated} recurring invoice(s) generated.', 'info')
        # ... rest of dashboard queries ...
```

### Dashboard -> Overdue Detection

**Trigger:** dashboard agent's `index` route
**Action:** Update overdue invoices directly in the same db connection.

```python
# In dashboard/routes.py index, after recurring generation:
db.execute("""
    UPDATE invoices SET status = 'overdue', updated_at = datetime('now')
    WHERE user_id = ? AND status = 'sent' AND due_date < date('now')
""", (user_id,))
# Commit happens after all dashboard setup queries
```

### Payment -> Invoice Status Update

**Trigger:** payments agent's `create_payment` route, after inserting payment
**Action:** Check if invoice is fully paid and update status.

```python
# In payments/routes.py create_payment, after INSERT:
total_paid = db.execute(
    "SELECT COALESCE(SUM(amount_cents), 0) FROM payments WHERE invoice_id = ?",
    (invoice_id,)
).fetchone()[0]
invoice_total = db.execute(
    "SELECT total_cents FROM invoices WHERE id = ?",
    (invoice_id,)
).fetchone()['total_cents']

if total_paid >= invoice_total:
    db.execute("UPDATE invoices SET status = 'paid', updated_at = datetime('now') WHERE id = ?", (invoice_id,))
    if total_paid > invoice_total:
        flash('Warning: Overpayment recorded.', 'warning')
# Route handler commits after all operations
```

---

## Coordinated Behaviors Table

These behaviors must be consistent across all agents. If in doubt, match this table exactly.

### Flash Messages

| Event | Flash Category | Message Pattern | Which Agent |
|-------|---------------|-----------------|-------------|
| Record created | success | "{Type} created successfully." | All CRUD agents |
| Record updated | success | "{Type} updated successfully." | All CRUD agents |
| Record deleted | success | "{Type} deleted." | All CRUD agents |
| Validation error | danger | Specific field message | All form agents |
| Login required | warning | "Please log in to access this page." | helpers.py (decorator) |
| Auth failed | danger | "Invalid email or password." | auth |
| Registered | success | "Registration successful. Please log in." | auth |
| Invoice duplicated | success | "Invoice duplicated as draft {number}." | invoices |
| Deal won | success | 'Deal "{title}" marked as Won! Create an invoice?' | pipeline |
| Status changed | success | "Invoice status updated to {status}." | invoices |
| Recurring generated | info | "{N} recurring invoice(s) generated." | dashboard |
| Overpayment | warning | "Warning: Overpayment recorded." | payments |
| Not found | danger | "{Type} not found." | All agents (404 on owned entities) |

### Activity Logging

These specific events automatically create an activity log entry. The activity is created in the SAME transaction as the triggering action (does NOT commit).

| Event | Activity Type | Notes Content | Which Agent Creates |
|-------|--------------|---------------|-------------------|
| Invoice created for client | note | "Invoice {number} created" | invoices |
| Invoice status changed | note | "Invoice {number} status: {old} -> {new}" | invoices |
| Payment recorded | note | "Payment of {amount} recorded on invoice {number}" | payments |
| Deal created for client | note | "Deal '{title}' created" | pipeline |
| Deal stage changed | note | "Deal '{title}' moved to {stage}" | pipeline |

```python
# Pattern for activity logging (all agents use this exact pattern):
def log_activity(db, client_id, user_id, activity_type, notes):
    """Log an activity. Does NOT commit."""
    if client_id:  # only log if there's a client
        db.execute("""
            INSERT INTO activities (client_id, user_id, type, notes, activity_date)
            VALUES (?, ?, ?, ?, date('now'))
        """, (client_id, user_id, activity_type, notes))
```

---

## Swarm Agent Assignment

**Total agents:** 15
**Total files:** 80 (71 app files from project structure + 9 test files owned by tests agent)
**Validation:** No file appears in multiple assignments. All 71 project-structure files are covered exactly once across agents 1-14. Agent 15 owns 9 test files not listed in the project structure tree (tests/ directory is an additive addition with zero overlap).

### Agent: scaffold
**Files:**
- `invoice-crm/run.py`
- `invoice-crm/requirements.txt`
- `invoice-crm/.gitignore`
- `invoice-crm/app/__init__.py`
- `invoice-crm/app/config.py`
- `invoice-crm/app/db.py`
- `invoice-crm/app/helpers.py`
- `invoice-crm/app/templates/base.html`

**Responsibility:** Creates the project entry point, app factory, database layer, shared helpers, and base template that all other agents depend on.

---

### Agent: auth
**Files:**
- `invoice-crm/app/auth/__init__.py`
- `invoice-crm/app/auth/routes.py`
- `invoice-crm/app/auth/forms.py`
- `invoice-crm/app/auth/templates/auth/login.html`
- `invoice-crm/app/auth/templates/auth/register.html`
- `invoice-crm/app/auth/templates/auth/profile.html`

**Responsibility:** Implements session-based authentication (login, register, logout) and the user business profile edit page.

---

### Agent: clients
**Files:**
- `invoice-crm/app/clients/__init__.py`
- `invoice-crm/app/clients/routes.py`
- `invoice-crm/app/clients/forms.py`
- `invoice-crm/app/clients/templates/clients/list.html`
- `invoice-crm/app/clients/templates/clients/detail.html`
- `invoice-crm/app/clients/templates/clients/form.html`

**Responsibility:** Implements full CRUD for clients including tag management, search/filter/sort on list, and the detail page aggregating invoices, payments, and activities.

---

### Agent: activities
**Files:**
- `invoice-crm/app/activities/__init__.py`
- `invoice-crm/app/activities/routes.py`
- `invoice-crm/app/activities/forms.py`
- `invoice-crm/app/activities/templates/activities/form.html`
- `invoice-crm/app/activities/templates/activities/list.html`

**Responsibility:** Implements activity log CRUD nested under the clients prefix, with type/date/notes form and a list partial reusable by the client detail page.

---

### Agent: pipeline
**Files:**
- `invoice-crm/app/pipeline/__init__.py`
- `invoice-crm/app/pipeline/routes.py`
- `invoice-crm/app/pipeline/forms.py`
- `invoice-crm/app/pipeline/templates/pipeline/list.html`
- `invoice-crm/app/pipeline/templates/pipeline/detail.html`
- `invoice-crm/app/pipeline/templates/pipeline/form.html`
- `invoice-crm/app/pipeline/templates/pipeline/kanban.html`

**Responsibility:** Implements the sales pipeline kanban view, deal CRUD, stage transitions (including the deal-won redirect to invoice creation), and activity logging on deal events.

---

### Agent: catalog
**Files:**
- `invoice-crm/app/catalog/__init__.py`
- `invoice-crm/app/catalog/routes.py`
- `invoice-crm/app/catalog/forms.py`
- `invoice-crm/app/catalog/templates/catalog/list.html`
- `invoice-crm/app/catalog/templates/catalog/form.html`

**Responsibility:** Implements CRUD for product/service catalog items with cents-based price storage and a unit dropdown.

---

### Agent: invoices
**Files:**
- `invoice-crm/app/invoices/__init__.py`
- `invoice-crm/app/invoices/routes.py`
- `invoice-crm/app/invoices/forms.py`
- `invoice-crm/app/invoices/templates/invoices/list.html`
- `invoice-crm/app/invoices/templates/invoices/detail.html`
- `invoice-crm/app/invoices/templates/invoices/form.html`
- `invoice-crm/app/invoices/templates/invoices/line_items_partial.html`

**Responsibility:** Implements invoice CRUD with line items, auto-numbering, status transitions, duplicate, from-deal prefill, and activity logging on create and status change.

---

### Agent: recurring
**Files:**
- `invoice-crm/app/recurring/__init__.py`
- `invoice-crm/app/recurring/routes.py`
- `invoice-crm/app/recurring/templates/recurring/settings.html`
- `invoice-crm/app/recurring/templates/recurring/history.html`

**Responsibility:** Implements recurrence settings, child invoice history view, and the `generate_due_invoices(db, user_id)` function imported by the dashboard agent.

---

### Agent: payments
**Files:**
- `invoice-crm/app/payments/__init__.py`
- `invoice-crm/app/payments/routes.py`
- `invoice-crm/app/payments/forms.py`
- `invoice-crm/app/payments/templates/payments/form.html`
- `invoice-crm/app/payments/templates/payments/list.html`

**Responsibility:** Implements payment recording with automatic invoice-status update on full payment, overpayment warning, activity logging, and the full payments list.

---

### Agent: dashboard
**Files:**
- `invoice-crm/app/dashboard/__init__.py`
- `invoice-crm/app/dashboard/routes.py`
- `invoice-crm/app/dashboard/templates/dashboard/index.html`

**Responsibility:** Implements the main dashboard that triggers recurring invoice generation, overdue detection, and displays revenue summaries, pipeline value, and top clients.

---

### Agent: reports
**Files:**
- `invoice-crm/app/reports/__init__.py`
- `invoice-crm/app/reports/routes.py`
- `invoice-crm/app/reports/templates/reports/index.html`
- `invoice-crm/app/reports/templates/reports/revenue_by_month.html`
- `invoice-crm/app/reports/templates/reports/revenue_by_client.html`
- `invoice-crm/app/reports/templates/reports/aging.html`
- `invoice-crm/app/reports/templates/reports/forecast.html`

**Responsibility:** Implements all report views (revenue by month, by client, aging, pipeline forecast) and CSV export for each report type.

---

### Agent: settings
**Files:**
- `invoice-crm/app/settings_bp/__init__.py`
- `invoice-crm/app/settings_bp/routes.py`
- `invoice-crm/app/settings_bp/forms.py`
- `invoice-crm/app/settings_bp/templates/settings_bp/index.html`

**Responsibility:** Implements the business settings page (named settings_bp to avoid Python stdlib conflict) for editing company info, invoice prefix, tax rate, currency, and payment terms.

---

### Agent: search
**Files:**
- `invoice-crm/app/search/__init__.py`
- `invoice-crm/app/search/routes.py`
- `invoice-crm/app/search/templates/search/results.html`

**Responsibility:** Implements global search across clients, invoices, and deals with results grouped by type and linked to their detail pages.

---

### Agent: static
**Files:**
- `invoice-crm/app/static/css/style.css`
- `invoice-crm/app/static/js/app.js`

**Responsibility:** Implements custom CSS overrides (kanban cards, overdue highlighting, dashboard layout) and vanilla JS for the invoice line-item dynamic form rows and catalog item autofill.

---

### Agent: tests
**Files:**
- `invoice-crm/tests/__init__.py`
- `invoice-crm/tests/conftest.py`
- `invoice-crm/tests/test_auth.py`
- `invoice-crm/tests/test_clients.py`
- `invoice-crm/tests/test_invoices.py`
- `invoice-crm/tests/test_payments.py`
- `invoice-crm/tests/test_pipeline.py`
- `invoice-crm/tests/test_dashboard.py`

**Responsibility:** Implements the full pytest suite (minimum 30 tests) covering all blueprint key routes, invoice total calculation, payment-to-status flow, deal-won redirect, overdue detection, and recurring generation.

---

## Acceptance Tests

### Happy Path
- WHEN a user registers with valid email and password THE SYSTEM SHALL create the account and redirect to login
- WHEN a user logs in with valid credentials THE SYSTEM SHALL set session and redirect to dashboard
- WHEN a user creates a client THE SYSTEM SHALL save the client and redirect to client list
- WHEN a user creates a deal THE SYSTEM SHALL save the deal and show it in pipeline view
- WHEN a user moves a deal to "won" THE SYSTEM SHALL redirect to invoice creation with client prefilled
- WHEN a user creates a catalog item THE SYSTEM SHALL save with price in cents
- WHEN a user creates an invoice with line items THE SYSTEM SHALL calculate subtotal, tax, and total correctly
- WHEN a user changes invoice status to "sent" THE SYSTEM SHALL update the status and log activity
- WHEN a user records a full payment THE SYSTEM SHALL mark invoice as "paid"
- WHEN a user records a partial payment THE SYSTEM SHALL keep invoice status unchanged
- WHEN a user records an overpayment THE SYSTEM SHALL mark as "paid" and show warning
- WHEN a user duplicates an invoice THE SYSTEM SHALL create a new draft with same line items and new number
- WHEN a recurring invoice is due THE SYSTEM SHALL generate a draft on dashboard load
- WHEN an invoice is past due date with status "sent" THE SYSTEM SHALL mark as "overdue" on dashboard load
- WHEN a user searches for "Acme" THE SYSTEM SHALL return matching clients, invoices, and deals
- WHEN a user exports a report as CSV THE SYSTEM SHALL return a downloadable CSV file

### Error Cases
- WHEN a user registers with an existing email THE SYSTEM SHALL show error and not create duplicate
- WHEN a user submits an invoice form with mismatched line item arrays THE SYSTEM SHALL reject and flash error
- WHEN a user accesses another user's data THE SYSTEM SHALL return 404 (all queries filter by user_id)
- WHEN a user accesses a route without login THE SYSTEM SHALL redirect to login with flash message

### Verification Commands
```bash
# Start the app
cd invoice-crm && python run.py

# Run tests
cd invoice-crm && python -m pytest tests/ -v

# Check all routes respond
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/auth/login  # 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/  # 302 (redirect to login)
```

---

## Feed-Forward

- **Hardest decision:** Whether to have the dashboard agent import directly from recurring.routes (cross-agent import) vs duplicating the generation logic. Chose direct import because it's the spec-prescribed exception to the "no cross-agent imports" rule -- the alternative (duplicate logic) is worse.
- **Rejected alternatives:** (1) Background job for recurring/overdue -- rejected as overkill for MVP, page-load check is simpler. (2) Dedicated "integration" agent to wire cross-boundary flows -- rejected because the wiring is small (2 cross-imports) and can be prescribed in spec. (3) Fewer agents (10) with merged blueprints -- rejected per user request for 15+.
- **Least confident:** The invoice line items form with parallel arrays (descriptions[], quantities[], unit_prices[], tax_rates[], catalog_item_ids[]) and the JS to add/remove rows. This is the most complex frontend interaction and the most likely place for a subtle bug (array length mismatch, cents conversion on save).

STATUS: PASS
