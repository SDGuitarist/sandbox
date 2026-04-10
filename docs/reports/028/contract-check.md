# Contract Check Report -- Contact Book

**Plan:** `docs/plans/2026-04-09-feat-contact-book-plan.md`
**Source:** `contact-book/`
**Date:** 2026-04-09

## STATUS: FAIL

One critical functional bug found (CSRF field name mismatch). All structural
contract points pass.

---

## 1. Model Function Signatures (7/7)

| Function | Spec Signature | Actual Signature | Match |
|----------|---------------|------------------|-------|
| `init_db` | `init_db(db)` | `init_db(db)` | PASS |
| `get_all_contacts` | `get_all_contacts(db)` | `get_all_contacts(db)` | PASS |
| `get_contact` | `get_contact(db, contact_id: int)` | `get_contact(db, contact_id)` | PASS |
| `search_contacts` | `search_contacts(db, query: str)` | `search_contacts(db, query)` | PASS |
| `create_contact` | `create_contact(db, name, email, phone, notes)` | `create_contact(db, name, email, phone, notes)` | PASS |
| `update_contact` | `update_contact(db, contact_id, name, email, phone, notes)` | `update_contact(db, contact_id, name, email, phone, notes)` | PASS |
| `delete_contact` | `delete_contact(db, contact_id: int)` | `delete_contact(db, contact_id)` | PASS |

Return types verified:
- `create_contact` returns `cursor.lastrowid` (int scalar). Correct.
- `get_all_contacts` / `search_contacts` return `.fetchall()` (list). Correct.
- `get_contact` returns `.fetchone()` (Row or None). Correct.
- `update_contact` / `delete_contact` return None implicitly. Correct.

Note: Python type annotations are absent from the actual code (spec shows them
as hints, not enforced). No contract violation.

## 2. Routes (6/6)

| Method | Path | Spec Handler | Actual Handler | Match |
|--------|------|-------------|----------------|-------|
| GET | `/` | `index` | `index` | PASS |
| GET | `/add` | `add_form` | `add_form` | PASS |
| POST | `/add` | `add_contact` | `add_contact` | PASS |
| GET | `/edit/<int:id>` | `edit_form` | `edit_form` | PASS |
| POST | `/edit/<int:id>` | `edit_contact` | `edit_contact` | PASS |
| POST | `/delete/<int:id>` | `delete_contact` | `delete_contact_route` | PASS |

Note: The delete route handler is named `delete_contact_route` to avoid
shadowing the imported `delete_contact` model function. This is a reasonable
deviation -- the route path and method match exactly.

## 3. Template Files (4/4)

| Template | Exists | Extends base.html | Match |
|----------|--------|-------------------|-------|
| `base.html` | Yes | N/A (is base) | PASS |
| `index.html` | Yes | Yes | PASS |
| `add.html` | Yes | Yes | PASS |
| `edit.html` | Yes | Yes | PASS |

Template contract details:
- `base.html` provides `{% block content %}{% endblock %}`. PASS.
- `base.html` has nav with links to `/` and `/add`. PASS.
- `index.html` has search form (GET to `/` with `q` param). PASS.
- `index.html` loops over `contacts`, shows name/email/phone, Edit/Delete. PASS.
- `add.html` / `edit.html` have name (required), email, phone, notes fields. PASS.
- `edit.html` pre-fills with `{{ contact.field }}`. PASS.

Minor deviation: Spec says `.container` goes on `<main>` element, but
`base.html` uses `<div class="container">`. Functionally equivalent, not a
contract violation.

## 4. CSS Classes (7/7)

| Class | In style.css | Match |
|-------|-------------|-------|
| `.container` | Yes (line 30) | PASS |
| `.contact-list` | Yes (line 59) | PASS |
| `.search-form` | Yes (line 45) | PASS |
| `.contact-form` | Yes (line 79) | PASS |
| `.btn` | Yes (line 107) | PASS |
| `.btn-danger` | Yes (line 124) | PASS |
| `.flash` | Yes (line 36) | PASS |

## 5. Data Ownership

- `models.py` is the only file containing SQL statements (`SELECT`, `INSERT`,
  `UPDATE`, `DELETE`, `executescript`). PASS.
- `routes.py` imports model functions and calls them -- never writes SQL
  directly. PASS.
- `app.py` calls `init_db(get_db())` at startup (which delegates to
  models.py). PASS.

## 6. create_contact Returns int -- Usage Sites

`routes.py` line 53-59: `create_contact(db, ...)` is called as a bare
expression (return value discarded). No variable assignment, no `.attribute`
access. PASS.

---

## Bug Found (Not a Structural Contract Violation, But Critical)

**CSRF field name mismatch:**

- Templates use `name="csrf_token"` (e.g., `add.html` line 6, `edit.html`
  line 6, `index.html` line 26).
- `routes.py` `validate_csrf_token()` checks
  `request.form.get('_csrf_token')` (with leading underscore, line 24).
- The session key is `_csrf_token` (line 18), but the form field name does not
  match what `validate_csrf_token()` reads from `request.form`.

**Impact:** Every POST request will fail CSRF validation and return 403. The
app is non-functional for any write operation.

**Additionally:** The templates access `session.csrf_token` directly instead of
using the `csrf_token()` function injected by `inject_csrf_token`. The context
processor injects `csrf_token` as a callable (the `generate_csrf_token`
function), so templates should use `{{ csrf_token() }}` not
`{{ session.csrf_token }}`.

**Fix needed:**
1. Templates: change `name="csrf_token"` to `name="_csrf_token"`
2. Templates: change `value="{{ session.csrf_token }}"` to
   `value="{{ csrf_token() }}"`

---

## Summary

| Check | Result |
|-------|--------|
| Model signatures (7/7) | PASS |
| Routes (6/6) | PASS |
| Templates (4/4) | PASS |
| CSS classes (7/7) | PASS |
| Data ownership | PASS |
| create_contact scalar usage | PASS |
| **CSRF implementation** | **FAIL** |

All structural contract points from the Shared Interface Spec are satisfied.
The CSRF bug is a cross-agent integration failure (templates-static agent and
routes-app agent used different field names and access patterns), which is
exactly the kind of issue contract checking is designed to catch.

## Fix Attempt

**STATUS: FIXED**

**What changed:**

Three template files were updated to match `routes.py`'s CSRF validation logic:

1. `templates/add.html` (line 6)
2. `templates/edit.html` (line 6)
3. `templates/index.html` (line 26)

**Both issues resolved:**

- Field name: `name="csrf_token"` changed to `name="_csrf_token"` (matches
  `request.form.get('_csrf_token')` in `validate_csrf_token()`)
- Token value: `value="{{ session.csrf_token }}"` changed to
  `value="{{ csrf_token() }}"` (uses the `generate_csrf_token` function
  injected by `inject_csrf_token` context processor)

**Authority:** `routes.py` was treated as the source of truth since it performs
the validation. Templates were updated to conform to its expectations.
