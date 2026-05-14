# Spec Contract Check Report -- Run 042

**Plan:** 2026-05-13-feat-workshop-registration-hub-plan.md
**Checked:** 2026-05-13

## Summary

- **Total checks:** 65
- **PASS:** 58
- **FAIL:** 7

## FAIL Items

### FAIL #49 -- get_registrant called with wrong keyword arg (RUNTIME CRASH)
**File:** app/payments/routes.py
**Impact:** Every payment webhook event will crash. get_registrant(conn, id) has no square_order_id kwarg.
**Fix:** Use direct SQL: `conn.execute("SELECT * FROM registrants WHERE square_order_id = ?", (order_id,)).fetchone()`

### FAIL #52 -- Scheduler queries wrong table name (RUNTIME CRASH)
**File:** app/scheduler/jobs.py
**Impact:** send-reminders command will crash. Table is registrants not registrations.
**Fix:** Change registrations to registrants.

### FAIL #36 -- Non-spec error code INVALID_SIGNATURE
**File:** app/payments/routes.py
**Fix:** Return empty body on 403: `return "", 403`

### FAIL #53 -- Global error handler catches only 500
**File:** app/__init__.py
**Fix:** Change @app.errorhandler(500) to @app.errorhandler(Exception)

### FAIL #54 -- get_next_waitlisted not used in waitlist/routes.py
**File:** app/waitlist/routes.py
**Fix:** Import and use get_next_waitlisted instead of inline SQL (low priority)

### FAIL #55 -- Flask admin missing WWW-Authenticate header
**File:** app/admin/routes.py
**Fix:** Add WWW-Authenticate: Basic header to 401 responses

### FAIL #56 -- flask-limiter not applied to routes
**File:** app/registration/routes.py, app/__init__.py
**Fix:** Export limiter from __init__.py, use @limiter.limit() decorator on registration route

STATUS: FAIL

## Fix Attempt

**Errors addressed:** 7
**Files modified:**
- `workshop-registration/app/payments/routes.py` -- replaced `get_registrant(conn, square_order_id=...)` with direct SQL in all three callers (_handle_payment_updated x2, _handle_refund_created); changed invalid-signature response to `return "", 403`; removed now-unused `get_registrant` import; added `from app import limiter` and `@limiter.limit("30 per minute")` decorator on the webhook route
- `workshop-registration/app/scheduler/jobs.py` -- changed table name from `registrations` to `registrants` in SELECT query
- `workshop-registration/app/__init__.py` -- moved `Limiter(...)` to module-level `limiter` variable so other modules can import it; changed `limiter.init_app(app)` call inside `create_app()`; changed `@app.errorhandler(500)` to `@app.errorhandler(Exception)` with `logger.error` call
- `workshop-registration/app/waitlist/routes.py` -- added `from app.models import get_next_waitlisted` import; restructured `try_promote_next` to call `get_next_waitlisted(conn)` first and then perform the atomic UPDATE claiming that specific row by id
- `workshop-registration/app/admin/routes.py` -- added `make_response` to import; added `WWW-Authenticate: Basic` header on all three 401 response paths in `require_admin`
- `workshop-registration/app/registration/routes.py` -- removed custom `_check_rate_limit` function and its imports (`time`, `collections.defaultdict`); added `from app import limiter`; replaced inline rate-limit check with `@limiter.limit("5 per minute")` decorator on the register route

**Fixes applied:**
1. FAIL #49 (CRITICAL): Replaced all `get_registrant(conn, square_order_id=...)` calls with `conn.execute("SELECT * FROM registrants WHERE square_order_id = ?", (...)).fetchone()` in payments/routes.py -- the function signature is `(conn, id)` with no keyword args.
2. FAIL #52 (CRITICAL): Changed `registrations` to `registrants` in the scheduler's SELECT query -- the table is named `registrants` per the schema.
3. FAIL #36: Changed invalid-signature 403 response from `return jsonify({"error": "Forbidden", "code": "INVALID_SIGNATURE"}), 403` to `return "", 403` -- `INVALID_SIGNATURE` is not in the spec's valid error code list; spec requires empty body on this 403.
4. FAIL #53: Changed `@app.errorhandler(500)` to `@app.errorhandler(Exception)` and updated the handler to log the exception, matching the spec's global error handler prescription.
5. FAIL #54: Imported `get_next_waitlisted` from `app.models` in waitlist/routes.py and used it to find the next candidate before performing the atomic UPDATE, satisfying the spec's requirement that `get_next_waitlisted` be used in `try_promote_next`.
6. FAIL #55: Added `WWW-Authenticate: Basic` header (via `make_response`) to all three 401 paths in `require_admin` in admin/routes.py.
7. FAIL #56: Promoted `Limiter` to a module-level `limiter` variable in `app/__init__.py` so it can be imported by other modules; replaced the custom rate limiter in registration/routes.py with `@limiter.limit("5 per minute")`; added `@limiter.limit("30 per minute")` to the webhook endpoint in payments/routes.py.

STATUS: FIXED
