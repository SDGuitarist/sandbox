# Contract Check: Bookmark Manager Assembly

**Date:** 2026-04-09
**Branch:** swarm-024-assembly
**Plan:** docs/plans/2026-04-09-feat-bookmark-manager-plan.md

---

## 1. models.py -- Function Signatures & Constants

### Constants

- **ITEMS_PER_PAGE: Final[int] = 20** -- PASS
- **SORT_OPTIONS: Final[list[str]] = ['newest', 'oldest', 'a-z']** -- PASS
- **SORT_LABELS: Final[dict[str, str]]** -- PASS (matches spec values)
- **SORT_MAP: Final[dict[str, str]]** -- PASS (matches spec values)

### Bookmark Functions

- **get_all_bookmarks(conn, sort_order, limit, offset) -> list[sqlite3.Row]** -- PASS
- **get_bookmark(conn, bookmark_id) -> sqlite3.Row | None** -- PASS
- **get_bookmark_count(conn) -> int** -- PASS
- **get_bookmarks_by_url(conn, url) -> list[sqlite3.Row]** -- PASS
- **create_bookmark(conn, url, title, description) -> int** -- PASS (returns cursor.lastrowid)
- **update_bookmark(conn, bookmark_id, url, title, description) -> None** -- PASS (sets updated_at in UPDATE)
- **delete_bookmark(conn, bookmark_id) -> None** -- PASS

### Sort & Escape

- **_sort_clause(sort_order) -> str** -- PASS (raises ValueError for unknown, uses SORT_MAP)
- **_escape_like(term) -> str** -- PASS (escapes backslash, %, _)

### Tag Functions

- **get_all_tags(conn) -> list[sqlite3.Row]** -- PASS (includes bookmark_count via LEFT JOIN)
- **get_tag_by_name(conn, name) -> sqlite3.Row | None** -- PASS
- **get_or_create_tag(conn, name) -> int** -- PASS (lowercases, strips, uses INSERT OR IGNORE)
- **get_tags_for_bookmark(conn, bookmark_id) -> list[sqlite3.Row]** -- PASS
- **get_tags_for_bookmarks(conn, bookmark_ids) -> dict[int, list[sqlite3.Row]]** -- PASS (batch query, handles empty list)
- **set_bookmark_tags(conn, bookmark_id, tag_names) -> None** -- PASS (deletes existing, lowercases/strips, skips empty, calls cleanup_orphan_tags)
- **cleanup_orphan_tags(conn) -> None** -- PASS (correct DELETE SQL)

### Search Functions

- **search_bookmarks(conn, query, sort_order, limit, offset) -> list[sqlite3.Row]** -- PASS (splits on spaces, AND clauses, EXISTS subquery, LIKE ESCAPE, parameterized)
- **search_bookmark_count(conn, query) -> int** -- PASS
- **get_bookmarks_by_tag(conn, tag_name, sort_order, limit, offset) -> list[sqlite3.Row]** -- PASS
- **get_bookmarks_by_tag_count(conn, tag_name) -> int** -- PASS

### Type Hints

- **All functions have type hints** -- PASS

---

## 2. __init__.py -- CSRF & Root Route

- **SECRET_KEY = secrets.token_hex(24)** -- PASS (random per startup)
- **DB_PATH defaults to 'bookmarks.db'** -- PASS
- **init_db called in app_context** -- PASS
- **csrf_protect before_request** -- PASS (generates session token, validates POST, aborts 403)
- **inject_csrf context_processor** -- PASS
- **Root route '/' redirects to bookmarks.index** -- PASS
- **Blueprint registration with correct prefixes** -- PASS (/bookmarks, /tags)

---

## 3. bookmarks/routes.py -- Routes & Patterns

### validate_url

- **Signature: validate_url(url: str) -> str** -- PASS
- **Raises ValueError** -- PASS (empty, >2048, non-http(s), missing netloc)

### Route Function Names

| Spec Name | Code Name | Status |
|-----------|-----------|--------|
| index | index | PASS |
| new_bookmark | new_bookmark | PASS |
| create_bookmark_route | create_bookmark_route | PASS |
| edit_bookmark | edit_bookmark | PASS |
| update_bookmark_route | update_bookmark_route | PASS |
| delete_bookmark_route | delete_bookmark_route | PASS |
| show_bookmark | show_bookmark | PASS |

### Usage Patterns

- **fetch_page_title BEFORE get_db()** -- PASS (line 100 calls fetch before line 102 opens db)
- **immediate=True for writes** -- PASS (create, update, delete all use `get_db(immediate=True)`)
- **Same-transaction: create_bookmark + set_bookmark_tags** -- PASS (same `with get_db()` block)
- **Same-transaction: update_bookmark + set_bookmark_tags** -- PASS
- **Same-transaction: delete_bookmark + cleanup_orphan_tags** -- PASS
- **READ routes use get_db() without immediate** -- PASS
- **Page out of range redirects to page 1** -- PASS
- **Duplicate URL warning** -- PASS (flash 'warning' but allows save)

### Issue: fetch_page_title return used as title directly

- **fetch_page_title called only when title is empty** -- PASS (matches spec: "Auto-fetch title if title empty")

---

## 4. tags/routes.py -- Route Structure

| Spec Name | Code Name | Status |
|-----------|-----------|--------|
| index | index | PASS |
| show | show | PASS |

- **READ pattern with get_db() (no immediate)** -- PASS
- **Pagination with redirect on page > total_pages** -- PASS
- **Reuses bookmarks/list.html with tag_filter** -- PASS
- **Passes bookmark_tags, sort_options** -- PASS

---

## 5. fetch_title.py -- Signature & Timeout

- **FETCH_TIMEOUT: int = 3** -- PASS
- **fetch_page_title(url: str) -> str | None** -- PASS
- **Uses urllib.request.urlopen with timeout=FETCH_TIMEOUT** -- PASS
- **Reads at most 100_000 bytes** -- PASS
- **Regex for <title> with IGNORECASE | DOTALL** -- PASS
- **Returns None on any Exception** -- PASS

---

## 6. schema.sql -- Tables, Indexes, CHECK Constraints

- **PRAGMA foreign_keys = ON** -- PASS
- **bookmarks table: all columns, defaults, CHECK constraints** -- PASS
  - url CHECK(length <= 2048) -- PASS
  - title CHECK(length <= 500), DEFAULT '' -- PASS
  - description CHECK(length <= 2000), DEFAULT '' -- PASS
  - created_at/updated_at with strftime default -- PASS
- **tags table: id, name UNIQUE NOT NULL CHECK(length <= 50)** -- PASS
- **bookmark_tags table: composite PK, foreign keys with ON DELETE CASCADE** -- PASS
- **idx_bookmark_tags_tag_id** -- PASS
- **idx_bookmarks_created_at** -- PASS
- **idx_bookmarks_title** -- PASS

---

## 7. Templates -- CSRF Token in All POST Forms

### POST forms found:

1. **bookmarks/form.html** (create/edit form) -- `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">` -- PASS
2. **bookmarks/detail.html** (delete form) -- `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">` -- PASS

### GET forms (no CSRF needed):

- bookmarks/list.html search form (GET) -- N/A, correct
- bookmarks/list.html sort form (GET) -- N/A, correct

**All POST forms have CSRF tokens** -- PASS

---

## 8. Template Endpoint Names (Cross-Check)

Templates reference Flask url_for() endpoint names. These MUST match route function names.

| Template Reference | Expected Endpoint | Status |
|--------------------|-------------------|--------|
| `bookmarks.list_bookmarks` (layout.html:12,14; list.html:12,18,32; detail.html:7) | `bookmarks.index` | **FAIL** |
| `bookmarks.detail` (list.html:41) | `bookmarks.show_bookmark` | **FAIL** |
| `tags.list_tags` (layout.html:15) | `tags.index` | **FAIL** |
| `bookmarks.new_bookmark` (list.html:8) | `bookmarks.new_bookmark` | PASS |
| `bookmarks.edit_bookmark` (detail.html:47) | `bookmarks.edit_bookmark` | PASS |
| `bookmarks.delete_bookmark_route` (detail.html:48) | `bookmarks.delete_bookmark_route` | PASS |
| `bookmarks.update_bookmark_route` (form.html:8) | `bookmarks.update_bookmark_route` | PASS |
| `bookmarks.create_bookmark_route` (form.html:8) | `bookmarks.create_bookmark_route` | PASS |
| `tags.show` (list.html:48; detail.html:28) | `tags.show` | PASS |

### Details on FAIL items:

1. **`bookmarks.list_bookmarks`** -- Used 5 times across layout.html, list.html, detail.html. The actual route function is named `index` (line 44 of routes.py: `def index():`), so the correct endpoint is `bookmarks.index`. This will cause a `BuildError` at runtime.

2. **`bookmarks.detail`** -- Used 1 time in list.html:41. The actual route function is named `show_bookmark` (line 159 of routes.py: `def show_bookmark(id):`), so the correct endpoint is `bookmarks.show_bookmark`. This will cause a `BuildError` at runtime.

3. **`tags.list_tags`** -- Used 1 time in layout.html:15. The actual route function is named `index` (line 18 of tags/routes.py: `def index():`), so the correct endpoint is `tags.index`. This will cause a `BuildError` at runtime.

---

## Summary

| Category | Checks | Pass | Fail |
|----------|--------|------|------|
| models.py signatures | 22 | 22 | 0 |
| __init__.py | 7 | 7 | 0 |
| bookmarks/routes.py | 14 | 14 | 0 |
| tags/routes.py | 6 | 6 | 0 |
| fetch_title.py | 6 | 6 | 0 |
| schema.sql | 9 | 9 | 0 |
| CSRF in templates | 2 | 2 | 0 |
| Template endpoint names | 9 | 6 | 3 |

**Total: 75 checks, 72 PASS, 3 FAIL**

### Failing Items (all runtime-breaking):

1. **FAIL** -- Templates use `bookmarks.list_bookmarks` instead of `bookmarks.index` (5 occurrences across 3 files)
2. **FAIL** -- Templates use `bookmarks.detail` instead of `bookmarks.show_bookmark` (1 occurrence in list.html)
3. **FAIL** -- Templates use `tags.list_tags` instead of `tags.index` (1 occurrence in layout.html)

All three failures are in template `url_for()` calls that reference endpoint names not matching the actual route function names. These will cause Flask `BuildError` exceptions at runtime, making the app non-functional.

---

## STATUS: FAIL
