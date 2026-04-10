---
title: "feat: Contact Book App"
type: feat
status: active
date: 2026-04-09
swarm: true
origin: docs/brainstorms/2026-04-09-contact-book-brainstorm.md
feed_forward:
  risk: "Whether the refactored bash instructions produce zero permission prompts during a real swarm build"
  verify_first: true
---

# feat: Contact Book App

Verification build for the compound bash instruction refactor. Simple contact
CRUD app using the sandbox standard stack (Flask + SQLite + Jinja2).

(see brainstorm: docs/brainstorms/2026-04-09-contact-book-brainstorm.md)

## Acceptance Criteria

- [ ] Add contact with name (required), email, phone, notes (optional)
- [ ] View all contacts in a list
- [ ] Search contacts by name (case-insensitive LIKE query)
- [ ] Edit a contact
- [ ] Delete a contact
- [ ] CSRF protection on all POST forms
- [ ] SECRET_KEY from environment variable
- [ ] Form validation (name required, email format if provided)

## File List

```
contact-book/
  app.py              # Flask app factory, config, CSRF setup
  schema.sql          # SQLite CREATE TABLE
  models.py           # DB functions (CRUD + search)
  routes.py           # Flask routes (list, add, edit, delete, search)
  templates/
    base.html         # Base template with nav
    index.html        # Contact list + search form
    add.html          # Add contact form
    edit.html         # Edit contact form
  static/
    style.css         # Basic styling
  tests/
    test_app.py       # Pytest tests for all routes
  requirements.txt    # Flask, pytest
```

## Shared Interface Spec

### Database Schema

```sql
-- schema.sql
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Model Functions (models.py)

All functions take `db` (sqlite3.Connection) as first argument.

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `init_db` | `init_db(db)` | `None` | Execute schema.sql |
| `get_all_contacts` | `get_all_contacts(db)` | `list[sqlite3.Row]` | All contacts ordered by name |
| `get_contact` | `get_contact(db, contact_id: int)` | `sqlite3.Row or None` | Single contact by ID |
| `search_contacts` | `search_contacts(db, query: str)` | `list[sqlite3.Row]` | Contacts where name LIKE %query% (case-insensitive) |
| `create_contact` | `create_contact(db, name: str, email: str, phone: str, notes: str)` | `int` | Insert and return new contact ID |
| `update_contact` | `update_contact(db, contact_id: int, name: str, email: str, phone: str, notes: str)` | `None` | Update contact fields |
| `delete_contact` | `delete_contact(db, contact_id: int)` | `None` | Delete contact by ID |

**Usage example for scalar return:**
```python
contact_id = create_contact(db, "Alice", "alice@example.com", "555-0100", "Friend")
# contact_id is an int, NOT a Row object. Do not access contact_id.name
```

### Route Table (routes.py)

| Method | Path | Handler | Expected Status | Description |
|--------|------|---------|----------------|-------------|
| GET | `/` | `index` | 200 | List all contacts (or search results if `?q=` param) |
| GET | `/add` | `add_form` | 200 | Show add contact form |
| POST | `/add` | `add_contact` | 302 -> `/` | Create contact, redirect to list |
| GET | `/edit/<int:id>` | `edit_form` | 200 | Show edit form for contact |
| POST | `/edit/<int:id>` | `edit_contact` | 302 -> `/` | Update contact, redirect to list |
| POST | `/delete/<int:id>` | `delete_contact` | 302 -> `/` | Delete contact, redirect to list |

### App Factory (app.py)

```python
# app.py structure
import os
import sqlite3
from flask import Flask, g

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('contacts.db')
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-prod')
    app.teardown_appcontext(close_db)

    with app.app_context():
        from models import init_db
        init_db(get_db())

    from routes import bp
    app.register_blueprint(bp)
    return app

if __name__ == '__main__':
    create_app().run(debug=True)
```

### Template Contracts

**base.html:** Provides `{% block content %}{% endblock %}`. Includes nav with link to `/` and `/add`.

**index.html:** Extends base. Shows search form (GET to `/` with `q` param). Loops over `contacts` list. Each row shows name, email, phone with Edit and Delete links/buttons. Delete uses a POST form with CSRF token.

**add.html / edit.html:** Extends base. Form with fields: name (required), email, phone, notes (textarea). POST with CSRF token. Uses `{{ contact.field }}` for edit pre-fill.

### CSS Classes (static/style.css)

| Class | Element | Purpose |
|-------|---------|---------|
| `.container` | `<main>` | Max-width centered layout |
| `.contact-list` | `<table>` | Contact list table |
| `.search-form` | `<form>` | Search bar styling |
| `.contact-form` | `<form>` | Add/edit form styling |
| `.btn` | `<button>`, `<a>` | Button base style |
| `.btn-danger` | Delete button | Red destructive action |
| `.flash` | `<div>` | Flash message styling |

### Data Ownership

| Table | Owner (writes) | Readers |
|-------|---------------|---------|
| contacts | models.py | routes.py (via model functions only) |

Routes NEVER write SQL directly. All writes go through model functions.

## Plan Quality Gate

1. **What exactly is changing?** New contact-book/ directory with 10 files (app, models, routes, schema, 4 templates, CSS, tests).
2. **What must not change?** No files outside contact-book/. No changes to autopilot skill or agents.
3. **How will we know it worked?** All routes return expected status codes in smoke test. Pytest passes. Zero permission prompts during the build.
4. **What is the most likely way this plan is wrong?** The spec is straightforward. The real test is whether the refactored bash instructions work, not whether the app is correct.

## Feed-Forward

- **Hardest decision:** None -- standard pattern.
- **Rejected alternatives:** None.
- **Least confident:** Whether this swarm build runs with zero permission prompts. That is the entire purpose of this build.

## Swarm Agent Assignment

**Total agents:** 3
**Total files:** 11
**Validation:** No file appears in multiple assignments

### Shared Interface Spec (included in every agent's context)

All agents receive the full Shared Interface Spec from this plan document (Database Schema, Model Functions, Route Table, App Factory, Template Contracts, CSS Classes, Data Ownership). This is the coordination contract -- agents must not deviate from it.

### Agent: routes-app

**Files:**
- contact-book/app.py
- contact-book/routes.py
- contact-book/requirements.txt
- contact-book/tests/test_app.py

**Responsibility:** Build the Flask app factory, all route handlers, the requirements file, and the full test suite -- imports models.py functions per the shared interface spec but never writes SQL directly.

---

### Agent: models-schema

**Files:**
- contact-book/schema.sql
- contact-book/models.py

**Responsibility:** Build the SQLite schema and all CRUD/search model functions matching the exact signatures in the shared interface spec.

---

### Agent: templates-static

**Files:**
- contact-book/templates/base.html
- contact-book/templates/index.html
- contact-book/templates/add.html
- contact-book/templates/edit.html
- contact-book/static/style.css

**Responsibility:** Build all Jinja2 templates and CSS using the template contracts and CSS class names from the shared interface spec.

---

STATUS: PASS
