---
title: "Flask URL Shortener API"
date: 2026-04-05
status: ready
brainstorm: "docs/brainstorms/2026-04-05-flask-url-shortener-api.md"
feed_forward:
  risk: "Thread safety of click_count increment under concurrent SQLite writes"
  verify_first: true
---

# Flask URL Shortener API — Plan

## What exactly is changing?
A new Flask application will be created from scratch in `/workspace/url-shortener/`. It will expose three HTTP endpoints backed by a SQLite database.

## What must NOT change?
- The existing `cli-todo-app` project in `/workspace` must not be touched.
- No external dependencies beyond Flask and the Python standard library (sqlite3 is stdlib).

## How will we know it worked?
1. `POST /shorten` with a valid URL returns a JSON response with `short_code` and `short_url`.
2. `GET /<code>` issues a 302 redirect to the original URL.
3. `GET /stats/<code>` returns click count that increments with each redirect.
4. `GET /<invalid-code>` returns 404.
5. `POST /shorten` with a non-HTTP/HTTPS URL returns 400.

## What is the most likely way this plan is wrong?
SQLite concurrent write contention on `click_count` — mitigated by using `UPDATE links SET click_count = click_count + 1` (atomic at the SQL level) inside a transaction. Flask's dev server is single-threaded by default, so this is only a risk in production with a multi-threaded WSGI server.

---

## File Structure

```
/workspace/url-shortener/
├── app.py           # Flask app, routes, DB init
├── database.py      # SQLite connection helper, schema creation
├── shortener.py     # Short code generation (base62, random 6 chars)
└── requirements.txt # Flask only
```

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    original_url TEXT NOT NULL,
    short_code  TEXT NOT NULL UNIQUE,
    click_count INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

SQLite file: `url-shortener/urls.db` (created at app startup).

## Short Code Generation (`shortener.py`)

```python
import random, string

CHARSET = string.ascii_letters + string.digits  # 62 chars
CODE_LEN = 6

def generate_code():
    return ''.join(random.choices(CHARSET, k=CODE_LEN))
```

Collision handling: retry up to 5 times; raise an error if all 5 collide (astronomically unlikely at small scale).

## Endpoints (`app.py`)

### POST /shorten
- Body: `{"url": "https://..."}`
- Validate: must start with `http://` or `https://`
- Generate unique short code (retry on UNIQUE constraint violation)
- Insert into `links`
- Return 201: `{"short_code": "abc123", "short_url": "http://localhost:5000/abc123"}`
- Return 400 on invalid URL

### GET /<code>
- Look up `short_code` in `links`
- If not found: return 404 JSON `{"error": "not found"}`
- Increment `click_count` atomically: `UPDATE links SET click_count = click_count + 1 WHERE short_code = ?`
- Return 302 redirect to `original_url`

### GET /stats/<code>
- Look up `short_code` in `links`
- If not found: return 404 JSON `{"error": "not found"}`
- Return 200: `{"short_code": "...", "original_url": "...", "click_count": N, "created_at": "..."}`

## Implementation Order
1. `requirements.txt` — Flask pin
2. `shortener.py` — pure function, no dependencies
3. `database.py` — get_db(), init_db(), schema
4. `app.py` — Flask app with all three routes + error handlers

## Feed-Forward
- **Hardest decision:** Atomic click count increment — using SQL `UPDATE ... SET click_count = click_count + 1` instead of read-modify-write in Python to avoid race conditions.
- **Rejected alternatives:** Separate `clicks` log table — overkill for this scope; a counter column is sufficient.
- **Least confident:** Whether Flask's `g` object and `teardown_appcontext` are the right pattern for SQLite connection management — this is the standard Flask-SQLite pattern and should be fine.
