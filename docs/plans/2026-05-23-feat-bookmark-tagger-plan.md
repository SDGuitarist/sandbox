---
title: "feat: Bookmark Tagger"
type: feat
status: completed
date: 2026-05-23
feed_forward:
  risk: "SSRF via URL fetching -- user-provided URLs could target internal services or cloud metadata endpoints"
  verify_first: true
---

# feat: Bookmark Tagger

## Enhancement Summary

**Deepened on:** 2026-05-23
**Sections enhanced:** 5 (Database, URL Fetching, Routes, Search, Security)
**Research agents used:** Flask patterns, URL fetch research, Security sentinel, Simplicity reviewer, Performance oracle, Context7 Flask docs

### Key Improvements
1. Added SSRF protection (scheme allowlist) to URL fetching
2. Added charset detection and Content-Type validation to fetch_meta
3. Added input validation limits (URL length, tag count, tag name length)
4. Specified `<int:id>` route converter for delete route
5. Confirmed Jinja2 autoescaping handles XSS for fetched content

### New Considerations Discovered
- SSRF is the #1 security risk -- `urllib.urlopen` follows redirects and supports `file://` by default
- Jinja2 autoescaping is on by default in Flask for `.html` templates -- no extra work needed
- Tags-as-TEXT-column was considered but rejected: makes LIKE search on individual tags unreliable

## Overview

A lightweight throwaway Flask web app for saving and tagging bookmarks. Paste a URL, the app auto-fetches the page title and meta description, you add comma-separated tags, and it stores everything in SQLite. A single-page list view lets you search by keyword or filter by tag.

This is a test app to exercise the plan-flow pipeline. Keep it minimal.

## Problem Statement / Motivation

Testing the `/plan-flow` skill (plan -> deepen -> self-review -> Codex handoff). Need a small but real app with enough moving parts: a data model, URL fetching, form handling, and search.

## Proposed Solution

Single Flask app in `bookmark-tagger/` with this structure:

```
bookmark-tagger/
├── run.py
├── requirements.txt
├── app/
│   ├── __init__.py          # create_app factory, CSRF, routes (no blueprints)
│   ├── db.py                # init_db, get_db, close_db
│   ├── models.py            # bookmark/tag CRUD functions
│   ├── fetch_meta.py        # fetch_page_meta(url) -> {title, description}
│   └── templates/
│       ├── layout.html      # base template
│       └── index.html       # single page: form + bookmark list + search
└── bookmark_tagger.db       # SQLite (gitignored)
```

### Key decisions

- **No blueprints** -- single-page app, one route module is enough. Unlike `bookmark-manager/` which needed separate bookmark/tag management, this is simpler.
- **Single page** -- the form, search bar, and bookmark list all live on `index.html`. No detail pages, no separate tag management.
- **Comma-separated tags** -- user types `python, flask, tutorial` in one text input. No tag picker UI.
- **urllib only** -- match existing pattern from `bookmark-manager/app/fetch_title.py`. No requests/BeautifulSoup dependency.

## Technical Approach

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS bookmark_tags (
    bookmark_id INTEGER NOT NULL REFERENCES bookmarks(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (bookmark_id, tag_id)
);
```

### SQLite Configuration (from solution docs)

Per `docs/solutions/2026-04-05-flask-url-shortener-api.md`:
- Enable **WAL mode + 10s timeout** to prevent "database is locked" errors: `PRAGMA journal_mode=WAL` + `sqlite3.connect(db_path, timeout=10)`
- Enable **foreign keys**: `PRAGMA foreign_keys = ON` (required for ON DELETE CASCADE)
- Call `init_db()` once at startup in `create_app()`, never in `@before_request`

#### Research Insights (Database)

**Connection pattern** (from Flask official docs): Use `g.db` with `teardown_appcontext` for request-scoped connections:

```python
# init_db() -- called once at startup
def init_db(app):
    conn = sqlite3.connect(app.config['DATABASE'], timeout=10)
    conn.execute("PRAGMA journal_mode = WAL")  # WAL set once, persists across connections
    with app.open_resource('schema.sql', mode='r') as f:
        conn.executescript(f.read())
    conn.close()

# get_db() -- per-request connection
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")  # must be set per connection
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
```

Register `close_db` in `create_app()` with `app.teardown_appcontext(close_db)`. WAL mode is set once in `init_db()` (it persists in the database file); `foreign_keys` must be set per connection.

**Tag loading:** Load bookmarks and tags in a single JOIN query to avoid N+1. Group by bookmark_id in Python. Follow the `get_tags_for_bookmarks()` pattern from `bookmark-manager/app/models.py:58`.

### Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Show bookmark list with search/filter |
| POST | `/add` | Add a new bookmark |
| POST | `/delete/<int:id>` | Delete a bookmark |

#### Research Insights (Routes)

**Security:** Use Flask's `<int:id>` converter (not `<id>`) so the route rejects non-integer values before they reach any query. This eliminates SQL injection risk on the delete route.

### URL Fetching

`fetch_meta.py` -- fetch the `<title>` and `<meta name="description">` from the URL:

```python
def fetch_page_meta(url: str) -> dict:
    """Return {'title': str, 'description': str}. Both default to '' on failure."""
```

- 3-second timeout (match existing pattern)
- Read max 100KB of response
- Regex extraction (no HTML parser needed for just title + meta description)
- Return empty strings on any failure -- never block bookmark creation

#### Research Insights (URL Fetching)

**SSRF Protection:**
Before fetching, validate the URL scheme is `http` or `https` only. This blocks `file://`, `ftp://`, `gopher://` attacks:

```python
from urllib.parse import urlparse

def is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ('http', 'https') and parsed.hostname is not None
```

Call `is_safe_url()` before `urllib.request.urlopen()`.

**Accepted non-goal (SSRF depth):** This app is local-only (`127.0.0.1:5000`, never exposed on `0.0.0.0`). Scheme-only validation is formally accepted as sufficient. Private IP blocking, redirect-hop validation, and DNS rebinding protection are out of scope. If the app were ever exposed publicly, those would be required.

**Charset Detection:**
Extract charset from `Content-Type` header instead of always assuming UTF-8:

```python
charset = 'utf-8'
content_type = resp.headers.get('content-type', '')
m = re.search(r'charset=([^;\s]+)', content_type, re.IGNORECASE)
if m:
    charset = m.group(1).strip('"\'')
content = resp.read(100_000).decode(charset, errors='ignore')
```

**User-Agent Header:**
Set a User-Agent to avoid blocks from sites that reject default Python urllib:

```python
req = urllib.request.Request(url, headers={'User-Agent': 'BookmarkTagger/1.0'})
resp = urllib.request.urlopen(req, timeout=3)
```

**Content-Type Check:**
Skip fetching metadata from non-HTML responses (PDFs, images):

```python
if 'text/html' not in content_type.lower():
    return {'title': '', 'description': ''}
```

**Meta Description Regex:**
Handle both attribute orderings (`name` before `content` and vice versa):

```python
re.search(r'<meta\s+name=["\']?description["\']?\s+content=["\']([^"\']*)["\']', content, re.IGNORECASE)
```

### Search

Single text input (`q` parameter). Behavior:

- **Fields searched:** `bookmarks.title`, `bookmarks.url`, and `tags.name`
- **Matching:** Case-insensitive substring via `LIKE` with `COLLATE NOCASE`. All queries use parameterized SQL -- never string interpolation.
- **Escaping:** `%` and `_` in user input are escaped via `_escape_like()` (backslash-escape, `ESCAPE '\'` clause)
- **Tag filter:** `?tag=python` query parameter. Clicking a tag badge sets this parameter.
- **Combining `q` + `tag`:** `AND` -- both must match. Clicking a tag while searching narrows results.
- **Result ordering:** `created_at DESC` (newest first)
- **Empty results:** Show "No bookmarks found" message

### Orphan Tag Cleanup

After deleting a bookmark, clean up tags that no longer have any associated bookmarks. Use `DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM bookmark_tags)`. Same pattern as `bookmark-manager/app/models.py:78`.

### CSRF Protection

**Token lifecycle:**
1. **Created:** In `@app.before_request`, only if `csrf_token` is not already in `session`. Token is generated via `secrets.token_hex(16)` (CSPRNG). It does NOT rotate on every request -- it persists in the session until the session expires.
2. **Rendered:** Injected into templates via `@app.context_processor` as `{{ csrf_token }}`. Every POST form includes `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`.
3. **Validated:** On every POST request, compare `request.form.get('csrf_token')` against `session['csrf_token']` using `hmac.compare_digest()` (constant-time, prevents timing attacks).
4. **On mismatch:** Return `403 Forbidden` with a flash message "Invalid or missing CSRF token."

### Input Validation

Per security review, add these limits at the route handler level:

| Input | Limit | Behavior on violation |
|-------|-------|-----------------------|
| URL | Max 2048 chars | Flash error, reject |
| URL scheme | `http` or `https` only | Flash error, reject |
| Tag name | Max 50 chars, stripped/lowercased | Flash warning, truncate to 50 chars |
| Tag count | Max 20 per bookmark | Flash warning "Only first 20 tags kept", drop extras |

### XSS Protection

Jinja2 autoescaping is enabled by default for `.html` templates in Flask. Fetched titles and descriptions are user-controlled content but will be auto-escaped on render. Never use `| safe` on fetched strings.

## What Must Not Change

- No modifications to any existing app in the sandbox
- No changes to global CLAUDE.md or settings
- No external API calls beyond fetching the user-provided URL

## Acceptance Tests

All tests use Flask's test client (`app.test_client()`) with `fetch_page_meta` monkeypatched to return deterministic results. No live internet access required.

### Happy Path
- WHEN a user submits a valid URL THE SYSTEM SHALL save the bookmark with fetched title/description and redirect to `/` with the bookmark visible in the list
- WHEN a user submits a URL with tags `"python, flask, tutorial"` THE SYSTEM SHALL create 3 tags (lowercased, stripped) and associate them with the bookmark
- WHEN a user submits a URL with tag `"Python"` and tag `"python"` already exists THE SYSTEM SHALL reuse the existing tag (case-insensitive dedup)
- WHEN a user searches `?q=flask` THE SYSTEM SHALL return bookmarks matching "flask" in title, URL, or tag name (case-insensitive)
- WHEN a user filters `?tag=python` THE SYSTEM SHALL return only bookmarks tagged "python"
- WHEN a user searches `?q=tutorial&tag=python` THE SYSTEM SHALL return bookmarks matching both (AND)
- WHEN a user deletes a bookmark THE SYSTEM SHALL remove the bookmark, its `bookmark_tags` rows, and any orphaned tags

### Error Cases
- WHEN a user submits an empty URL THE SYSTEM SHALL flash an error and not create a bookmark
- WHEN a user submits `file:///etc/passwd` THE SYSTEM SHALL flash "Invalid URL scheme" and reject
- WHEN a user submits a URL where fetch returns empty (timeout/error) THE SYSTEM SHALL save the bookmark with title='' and description=''
- WHEN a user submits a URL longer than 2048 chars THE SYSTEM SHALL flash an error and reject
- WHEN a user submits a POST with missing/wrong CSRF token THE SYSTEM SHALL return 403
- WHEN a user submits 25 comma-separated tags THE SYSTEM SHALL keep the first 20 and flash a warning
- WHEN `fetch_page_meta` receives a non-HTML Content-Type THE SYSTEM SHALL return empty title/description
- WHEN a user deletes a nonexistent bookmark id THE SYSTEM SHALL redirect to `/` (no error, no crash)

### Verification Commands
```bash
# Run test suite (once tests exist)
cd bookmark-tagger
python3 -m pytest tests/ -v

# Manual smoke test
python3 run.py &
# Visit http://localhost:5000 in browser
# Add a bookmark, search, delete, verify tags
kill %1
```

## Dependencies & Risks

- **Dependencies:** Flask, Python 3.10+, SQLite3 (stdlib)
- **Risk:** URL fetching hangs on slow sites. Mitigated by 3-second timeout.
- **Risk:** Some sites block urllib's default User-Agent. Acceptable for a throwaway app.

## Implementation Files

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `run.py` | ~5 | App entry point |
| `requirements.txt` | ~2 | Flask dependency |
| `app/__init__.py` | ~30 | App factory, CSRF, routes |
| `app/db.py` | ~25 | SQLite init and connection helper |
| `app/models.py` | ~60 | Bookmark/tag CRUD + search |
| `app/fetch_meta.py` | ~20 | URL title/description fetcher |
| `app/templates/layout.html` | ~25 | Base HTML template |
| `app/templates/index.html` | ~60 | Form + list + search |

**Total: ~230 lines**

## Feed-Forward
- **Hardest decision:** Whether to do server-side URL fetching at all. It introduces SSRF risk, blocking I/O, and test complexity. Kept it because it's the core feature that makes this more than a plain CRUD form -- and the plan-flow pipeline benefits from reviewing a plan with real security/performance trade-offs. Accepted scheme-only SSRF validation as sufficient for a local-only app.
- **Rejected alternatives:** (1) No server-side fetch (user enters title manually or client-side JS fetch) -- removes SSRF/timeout concerns entirely but also removes the interesting security review surface. (2) Using requests + BeautifulSoup -- adds dependencies for marginal improvement. (3) Flat tags column -- makes LIKE search on individual tags unreliable ("go" matches "golang"). (4) Skipping CSRF -- only 10 lines, good habit even for throwaway. (5) Separate pages for add/edit/detail -- unnecessary for a test app.
- **Least confident:** SSRF protection depth. Scheme-only validation is formally accepted for local-only use (see URL Fetching section). If this app were ever exposed on `0.0.0.0`, private IP blocking and redirect-hop validation would be required. **Verify first:** Confirm `is_safe_url()` rejects `file://`, `ftp://`, and URLs with no hostname before implementing other routes.
