---
title: "Flask URL Shortener API with SQLite"
date: 2026-04-05
tags: [flask, sqlite, rest-api, python, url-shortener]
---

# Flask URL Shortener API — Solution Doc

## Problem Solved
Built a production-ready URL shortener REST API with Flask + SQLite. Three endpoints: POST /shorten (create), GET /<code> (302 redirect + click count), GET /stats/<code> (analytics).

## Key Decisions

### Short code generation: `secrets.choice` not `random.choices`
Use `secrets.choice` (CSPRNG) for short code generation, never `random.choices` (Mersenne Twister). Predictable PRNGs allow attackers to enumerate private short URLs from observed codes.

```python
import secrets, string
CHARSET = string.ascii_letters + string.digits
def generate_code():
    return ''.join(secrets.choice(CHARSET) for _ in range(6))
```

### `init_db()` once at startup, not on every request
Call `init_db(app)` in the `if __name__ == '__main__'` block using `with app.app_context()`. Never in `@app.before_request` — `executescript()` has an implicit COMMIT side effect that can silently close open transactions, and the per-request overhead is unnecessary.

```python
# Correct pattern
if __name__ == '__main__':
    init_db(app)
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
```

### SQLite WAL mode + busy timeout for concurrent writes
Default SQLite journal mode causes `OperationalError: database is locked` under concurrent writes. Enable WAL and set a timeout:

```python
g.db = sqlite3.connect(DATABASE, timeout=10)
g.db.execute('PRAGMA journal_mode=WAL')
```

### Atomic click count: SQL expression, not Python read-modify-write
```sql
UPDATE links SET click_count = click_count + 1 WHERE short_code = ?
```
Never do `read count → increment in Python → write back`. That's a TOCTOU race.

### 302 not 301 for redirects
Browsers permanently cache 301s and bypass the server on subsequent visits — click counts would stop incrementing. Always use 302 for analytics-tracked redirects.

### URL validation: scheme check + length cap
```python
MAX_URL_LENGTH = 2048
if not url or len(url) > MAX_URL_LENGTH or not url.startswith(('http://', 'https://')):
    return jsonify({'error': ...}), 400
```

### JSON error handlers for all Flask default HTML errors
Flask's default 404/405 handlers return HTML. Add JSON handlers for a consistent API:
```python
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404
```

## Risk Resolution
- **Risk tracked:** Thread safety of `click_count` increment under concurrent SQLite writes
- **What actually happened:** The SQL expression `click_count = click_count + 1` correctly avoids Python-level races, but SQLite's default journal mode (DELETE) still serializes writes with a file lock and raises `OperationalError` under load. Added `timeout=10` + WAL mode to mitigate.
- **Lesson:** "Atomic SQL expression" and "SQLite concurrent write safety" are two separate problems. Both must be addressed.

## File Structure
```
url-shortener/
├── app.py           # Flask app, routes, error handlers
├── database.py      # SQLite connection (WAL + timeout), schema init
├── shortener.py     # CSPRNG code generation
└── requirements.txt # Flask==3.0.3
```
