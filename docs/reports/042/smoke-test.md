# Smoke Test Report

**Plan:** 2026-05-13-feat-workshop-registration-hub-plan.md
**Tested:** 2026-05-13 23:16 PDT (2026-05-14T06:16Z)
**Run type:** Re-run to verify 3 previously reported bug fixes (proxy path stripping, EJS layout, Square error handling)

## App Startup

### Flask (Python)

- **Command:** `/Users/alejandroguillen/Projects/sandbox/workshop-registration/.venv/bin/python /tmp/run_flask_5001.py`
- **Status:** started
- **Time to ready:** ~5 seconds
- **Port note:** `run.py` hardcodes `port=5000`. macOS AirPlay Receiver occupies port 5000. A `/tmp/run_flask_5001.py` launcher started Flask on port 5001 with no source file modifications.

### Express (Node)

- **Command:** `bash /tmp/run_express2.sh` (sources `.env` from project root, sets `FLASK_API_URL=http://localhost:5001`, cd to `frontend/`, runs `node server.js`)
- **Status:** started
- **Time to ready:** ~3 seconds
- **Env note:** `server.js` calls `dotenv.config()` with no explicit path. When started from a directory other than `workshop-registration/frontend/`, dotenv finds no `.env` file. The launcher script explicitly sources `.env` before starting Node to ensure `ADMIN_PASSWORD` and other vars are present.

## Route Results

| # | Method | Path | Expected | Actual | Status | Notes |
|---|--------|------|----------|--------|--------|-------|
| 1 | GET | http://localhost:5000/api/health | 200 | 200 | PASS | Tested on port 5001 (AirPlay blocks 5000). Response: `{"db":"connected","status":"ok","supabase":"connected"}` |
| 2 | POST | http://localhost:3000/api/register | 201 or 500 | 500 | PASS | Square sandbox returns `INVALID_EMAIL_ADDRESS` for `test@example.com`. Route handles it gracefully: returns `{"code":"INTERNAL_ERROR","error":"Payment link creation failed"}`. No crash, correct JSON shape. |
| 3 | GET | http://localhost:3000/api/admin/registrants | 200 | 200 | PASS | Returns registrant array with `capacity`, `paid_count`, `total`, `waitlist_count` fields. Basic auth accepted and proxied to Flask correctly. |
| 4 | GET | http://localhost:3000/register | 200 | 200 | PASS | Full HTML page with `<title>Register - Amplify AI Workshop</title>` and `id="register-form"` form element present. |
| 5 | GET | http://localhost:3000/admin/ | 200 | 200 | PASS | Full HTML dashboard with `<title>Admin Dashboard - Workshop Registration</title>` and `id="registrant-table"` element present. Basic auth accepted. |

## Content Verification

| Route | Key Marker | Found |
|-------|-----------|-------|
| GET /api/health | `"status":"ok"` | Yes |
| GET /api/health | `"db":"connected"` | Yes |
| GET /api/health | `"supabase":"connected"` | Yes |
| GET /register | `<title>Register - Amplify AI Workshop</title>` | Yes |
| GET /register | `id="register-form"` | Yes |
| GET /admin/ | `<title>Admin Dashboard - Workshop Registration</title>` | Yes |
| GET /admin/ | `id="registrant-table"` | Yes |
| POST /api/register (500) | `{"code":"INTERNAL_ERROR","error":"Payment link creation failed"}` | Yes |

## Bug Verification (Previously Reported Fixes)

| Bug | Previous Run | This Run | Verdict |
|-----|-------------|----------|---------|
| B1 -- Proxy path stripping: `/api` prefix stripped before Flask received requests | FAIL (routes 2, 3 returned 500 with wrong path) | PASS -- routes 2 and 3 reach Flask with correct paths | FIXED |
| B2 -- EJS layout: `layout()` helper undefined in plain EJS, admin dashboard crashed | FAIL (route 5 returned 500) | PASS -- admin dashboard renders 200 with full HTML | FIXED |
| B3 -- Square error handling: unhandled `ApiError` propagated as crash | FAIL (route 2 crashed rather than returning clean error) | PASS -- returns graceful `{"code":"INTERNAL_ERROR","error":"Payment link creation failed"}` | FIXED |

## Summary

- **Total routes:** 5
- **PASS:** 5
- **FAIL:** 0

STATUS: PASS
