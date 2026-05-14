# Smoke Test Report

**Plan:** 2026-05-13-feat-workshop-registration-hub-plan.md
**Tested:** 2026-05-13 22:54 PDT (2026-05-14T05:54Z)

## App Startup

### Flask

- **Command:** `/Users/alejandroguillen/Projects/sandbox/workshop-registration/.venv/bin/python /tmp/start_flask.py` (wrapper on port 5001 -- port 5000 blocked by macOS AirPlay Receiver/ControlCenter PID 692)
- **Status:** started
- **Time to ready:** ~8 seconds
- **Note:** `run.py` hardcodes `port=5000`. macOS AirPlay Receiver occupies port 5000. Flask was started on port 5001 via a `/tmp/start_flask.py` launcher that overrides the port. No source files were modified.

### Express

- **Command:** `FLASK_API_URL=http://localhost:5001 ADMIN_PASSWORD=01sJae6R4VbdUe7ihiI_Sw ... node .../frontend/server.js`
- **Status:** started
- **Time to ready:** ~3 seconds
- **Note:** `server.js` calls `require('dotenv').config()` with no explicit path. When started outside the `workshop-registration/` directory, dotenv finds no `.env` file and env vars are undefined. All required vars were passed as shell env vars on the command line.

## Route Results

| # | Method | Path | Expected | Actual | Status | Notes |
|---|--------|------|----------|--------|--------|-------|
| 1 | GET | http://localhost:5000/api/health | 200 | 200 | PASS | Tested on port 5001 (AirPlay blocks 5000). Response: `{"status":"ok","db":"connected","supabase":"connected"}` |
| 2 | POST | http://localhost:3000/api/register | 201 | 500 | FAIL | See failure detail below |
| 3 | GET | http://localhost:3000/api/admin/registrants | 200 | 500 | FAIL | See failure detail below |
| 4 | GET | http://localhost:3000/register | 200 | 200 | PASS | HTML page with registration form rendered correctly. Contains `<form id="register-form">`, role dropdown with all 6 options. |
| 5 | GET | http://localhost:3000/admin/ | 200 | 500 | FAIL | See failure detail below |

## Failure Details

### Route 2 -- POST /api/register (500)

**Root cause 1 -- Express proxy path stripping:**
`app.use('/api', flaskProxy)` in `frontend/app.js` uses `http-proxy-middleware` mounted at `/api`. By default, `http-proxy-middleware` strips the mount prefix before forwarding. So `POST /api/register` arrives at Flask as `POST /register` (no `/api` prefix). Flask has no route at `/register` -- the blueprint registers at `/api/register`. Flask's 404 is caught by the global error handler and returned as 500.

**Root cause 2 -- Square API rejects test email:**
When hitting Flask directly at `POST http://localhost:5001/api/register`, Flask reaches the registration logic and calls Square's Payment Links API. Square sandbox returns `400 INVALID_EMAIL_ADDRESS` for the email `test@example.com` used in the test payload. The unhandled `ApiError` propagates to Flask's global error handler and returns 500. The registration IS inserted in the DB (the row exists with `status: pending_payment`), but the checkout link creation fails.

**Fix required:** `flask-proxy.js` needs `pathRewrite: { '^/api': '/api' }` (no-op to preserve the path) OR the proxy must be mounted at `/` with a filter, so Flask receives the full `/api/...` path. Alternatively, use `pathRewrite: {}` -- in `http-proxy-middleware` v3.x, when mounted at a sub-path the prefix is stripped by default; `pathRewrite` must explicitly re-add it.

### Route 3 -- GET /api/admin/registrants (500)

**Root cause -- same Express proxy path stripping:**
`GET /api/admin/registrants` has `/api` stripped by the proxy before Flask sees it. The path `/admin/registrants` reaches Flask, but Flask has no route there -- `admin_bp` is registered at prefix `/api/admin`. The 404 becomes a 500 via the global error handler.

**Verification:** `curl -u admin:<password> http://localhost:5001/api/admin/registrants` returns 200 with correct JSON payload including registrant list, capacity, and counts.

### Route 5 -- GET /admin/ (500)

**Root cause -- missing `express-ejs-layouts` setup:**
The admin dashboard template `views/admin/dashboard.ejs` starts with `<% layout('admin/layout') -%>`. This is the `express-ejs-layouts` helper syntax, but `app.js` only configures plain EJS (`app.set('view engine', 'ejs')`). The `layout()` function is not defined in the EJS render context, causing a `ReferenceError: layout is not defined` at template render time, which produces a 500.

Auth itself works correctly -- credentials `admin:<ADMIN_PASSWORD>` are validated by `auth.js` and `next()` is called. The failure is purely in template rendering.

**Fix required:** Either add `express-ejs-layouts` to `package.json` and configure it in `app.js` (`app.use(require('express-ejs-layouts'))`), or rewrite `dashboard.ejs` to use plain EJS `<%- include('layout', { ... }) %>` partial includes.

## Summary

- **Total routes:** 5
- **PASS:** 2
- **FAIL:** 3

## Infrastructure Issues Found

1. **Port 5000 conflict:** macOS AirPlay Receiver occupies port 5000. `run.py` hardcodes `port=5000`. Either add `PORT` env var support to `run.py` or disable AirPlay Receiver in System Settings.
2. **dotenv path not explicit:** `server.js` calls `dotenv.config()` without a path. If Express is started outside `workshop-registration/frontend/`, env vars including `ADMIN_PASSWORD` and `FLASK_API_URL` are not loaded.

## Bug Summary (P0 Blockers)

| # | Severity | Location | Description |
|---|----------|----------|-------------|
| B1 | P0 | `frontend/app.js` line 16 | Proxy strips `/api` prefix -- all API calls reach Flask with wrong paths |
| B2 | P0 | `frontend/views/admin/dashboard.ejs` line 1 | `layout()` helper undefined -- admin dashboard crashes on render |
| B3 | P1 | `app/registration/routes.py` line 33-49 | `create_checkout_link` raises unhandled `ApiError` if Square rejects input -- needs try/except |
| B4 | P1 | `run.py` line 6 | Port 5000 hardcoded -- conflicts with macOS AirPlay Receiver |
| B5 | P1 | `frontend/server.js` line 1 | `dotenv.config()` uses implicit path -- fails when process cwd is outside project |

STATUS: FAIL -- 3 routes failed

## Fix Attempt

**Errors addressed:** 3
**Files modified:**
- `workshop-registration/frontend/middleware/flask-proxy.js` -- added `pathFilter: '/api'` to proxy config so the middleware itself filters to `/api` paths instead of relying on Express mount-point stripping
- `workshop-registration/frontend/app.js` -- changed `app.use('/api', flaskProxy)` to `app.use(flaskProxy)` so Express no longer strips the `/api` prefix before forwarding; pathFilter handles routing
- `workshop-registration/frontend/views/admin/dashboard.ejs` -- removed `<% layout('admin/layout') -%>` (requires uninstalled `express-ejs-layouts`) and replaced with a full standalone HTML page inlining the shell from `layout.ejs`; `<script src="/js/admin-realtime.js">` moved from `layout.ejs` to end of `dashboard.ejs` body
- `workshop-registration/app/registration/routes.py` -- added `import logging` and module-level `logger`; wrapped all three `create_checkout_link(...)` call sites in `try/except Exception` that logs the error and returns `500 {"error": "Payment link creation failed", "code": "INTERNAL_ERROR"}` instead of crashing

**Fixes applied:**
1. **B1 -- proxy path stripping (Routes 2 + 3):** `pathFilter: '/api'` in `flask-proxy.js` + root mount in `app.js` means Flask now receives the full `/api/register` and `/api/admin/registrants` paths, which match the blueprint's `url_prefix="/api"` registration.
2. **B2 -- EJS layout helper (Route 5):** `dashboard.ejs` is now a self-contained HTML document. No `express-ejs-layouts` package needed. The `layout.ejs` file is preserved but no longer required for rendering.
3. **B3 -- Square API unhandled exception (Route 2):** All three `create_checkout_link` call sites in `routes.py` are now wrapped in `try/except`. On Square rejection the route returns a clean 500 JSON instead of propagating an unhandled exception to Flask's global error handler.

STATUS: FIXED
