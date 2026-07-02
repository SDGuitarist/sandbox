STATUS: PASS

# Contract Check — Run 080

## Summary

All spec contract invariants verified on assembled code. One issue found and fixed inline (flash categories).

## Checks Performed

### FC35 IDOR — Ownership Scoping (CRITICAL)
- PASS: `books.list` → `get_books_for_user(get_db(), session['user_id'], status)` — scoped
- PASS: `books.create` → `create_book(get_db(), session['user_id'], ...)` — scoped
- PASS: `books.edit` → `get_book_for_user(get_db(), book_id, session['user_id'])` — scoped
- PASS: `books.update` → `update_book(get_db(), book_id, session['user_id'], ...)` — scoped
- PASS: `books.delete` → `delete_book(get_db(), book_id, session['user_id'])` — scoped
- PASS: No book is queried by id alone. All 5 book DB calls include user_id.

### CSRF Token Syntax (with parentheses)
- PASS: `base.html` logout form — `{{ csrf_token() }}`
- PASS: `auth/register.html` — `{{ csrf_token() }}`
- PASS: `auth/login.html` — `{{ csrf_token() }}`
- PASS: `books/list.html` delete form — `{{ csrf_token() }}`
- PASS: `books/form.html` — `{{ csrf_token() }}`

### session.clear() on Login + Logout
- PASS: `auth.login` (line 65) — `session.clear()` before setting session keys
- PASS: `auth.logout` (line 76) — `session.clear()`

### SECRET_KEY Fail-Closed
- PASS: `__init__.py` raises `RuntimeError` when SECRET_KEY is absent (no dev fallback)

### Blueprint Names / Endpoints
- PASS: `bp = Blueprint('auth', __name__)` in auth.py
- PASS: `bp = Blueprint('books', __name__)` in books.py
- PASS: `auth_bp` registered (no prefix) + `books_bp` registered (`url_prefix='/books'`)

### Import Paths (Cross-Boundary Wiring)
- PASS: `from shelftrack.database import get_db, init_db` in `__init__.py`
- PASS: `from shelftrack.database import get_db` in `auth.py` and `books.py`
- PASS: `from shelftrack.auth_utils import login_required` in `auth.py` and `books.py`
- PASS: `from shelftrack.models import create_user, get_user_by_username` in `auth.py`
- PASS: `from shelftrack.models import create_book, get_books_for_user, get_book_for_user, update_book, delete_book` in `books.py`
- PASS: `from shelftrack import create_app` in `run.py`

### Authorization Matrix
- PASS: All 6 book routes decorated with `@login_required`
- PASS: `abort(404)` (never 403) for ownership failures in edit, update, delete

### Route Methods (explicit, no collisions)
- PASS: `books.list` GET / `books.create` POST on same path `` — disjoint methods declared
- PASS: `books.edit` GET / `books.update` POST on same path `/<int:book_id>/edit` — disjoint
- PASS: `auth.logout` POST only

### Password Hashing
- PASS: `generate_password_hash(password)` called before `create_user`
- PASS: `check_password_hash(user['password_hash'], password)` used in login

### autocommit=True
- PASS: Both `sqlite3.connect` calls use `autocommit=True` (not `isolation_level=None`)

### Flash Categories
- FIXED (inline, 1 retry): 8 error flash() calls were missing the `'error'` category
  (defaulted to `'message'`, breaking CSS class `flash-{{ category }}`).
  Fixed in `auth.py` (lines 29, 32, 36, 43) and `books.py` (lines 56, 64, 99, 107).
  Fix committed as 7f08f0e on swarm-080-assembly.

### StrictUndefined
- PASS: Not enabled — None-safe template idioms work correctly

## Result

STATUS: PASS (one issue fixed inline — flash categories missing 'error'; fixed on first retry)
