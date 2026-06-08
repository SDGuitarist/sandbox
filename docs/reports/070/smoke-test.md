STATUS: PASS

# Smoke Test — Run 070

## Result: 18/18 PASS

All smoke tests passed after one inline fix to database.py.

## Fix Applied (inline)

**Root cause:** `init_app()` used `os.path.exists(':memory:')` logic that called
`init_db()` which opened a separate SQLite connection. For `:memory:` databases,
each `connect(':memory:')` creates an isolated in-memory DB that is destroyed when
the connection closes. So the schema tables existed only in the `init_db()` connection
(closed at end of `init_app()`), but `get_db()` created a NEW connection on each
request with no tables.

**Fix:** For `:memory:` DATABASE config, create ONE persistent connection at app
startup, store it in `app.config['_MEMORY_DB']`, and have `get_db()` return it
for every request context. `close_db()` never closes this shared connection.
Non-memory databases are unaffected and retain the original behavior.

## Tests Passed

- GET /auth/login (200)
- GET /auth/register (200)
- GET / (redirect to login)
- Login form has CSRF token
- POST /auth/login (redirect)
- Login sets session['user_id']
- GET / (logged in, redirect to dashboard)
- GET /scenes/1 (200)
- GET /cast/1 (200)
- GET /crew/1 (200)
- GET /departments/1 (200)
- GET /locations/1 (200)
- GET /schedule/1 (200)
- GET /call-sheets/1 (200)
- GET /budget/1 (200)
- GET /expenses/1 (200)
- GET /reports/1 (200)
- CSP includes cdn.jsdelivr.net
