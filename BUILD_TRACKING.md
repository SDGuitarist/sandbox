# BUILD_TRACKING.md

## Run Info

| Field | Value |
|-------|-------|
| Project | Workshop Registration Hub |
| Spec | docs/plans/2026-05-13-feat-workshop-registration-hub-plan.md |
| Date | 2026-05-13 |
| Phases | 4 |
| Total Agents | 8 (Agent 9 deferred to post-assembly) |
| Build Method | swarm |

---

## AGENT_STATUS

### core-foundation (Agent 1) -- Phase 1
- **Status:** COMPLETED
- **Files created:** 10 (run.py, requirements.txt, schema.sql, .env.example, .gitignore, app/__init__.py, app/db.py, app/models.py, app/supabase_sync.py, app/webhooks.py)
- **Files modified:** 0
- **Issues encountered:** errorhandler(500) instead of Exception, flask-limiter not accessible from other modules
- **Commit:** e878215

### registration-admin-api (Agent 2) -- Phase 2
- **Status:** COMPLETED
- **Files created:** 4 (app/registration/__init__.py, app/registration/routes.py, app/admin/__init__.py, app/admin/routes.py)
- **Issues encountered:** Custom rate limiter instead of flask-limiter, missing WWW-Authenticate header, stale capacity check
- **Commit:** a20dea2

### payment-webhooks (Agent 3) -- Phase 2
- **Status:** COMPLETED
- **Files created:** 2 (app/payments/__init__.py, app/payments/routes.py)
- **Issues encountered:** Wrong function signature (get_registrant with square_order_id kwarg), invented error code INVALID_SIGNATURE
- **Commit:** ec2ad22

### email-engine (Agent 4) -- Phase 2
- **Status:** COMPLETED
- **Files created:** 2 (app/email/__init__.py, app/email/engine.py)
- **Issues encountered:** Fabricated checkout URL in _build_checkout_url()
- **Commit:** 721c5de

### waitlist-capacity (Agent 5) -- Phase 2
- **Status:** COMPLETED
- **Files created:** 2 (app/waitlist/__init__.py, app/waitlist/routes.py)
- **Issues encountered:** Inline SQL instead of model function, premature commit in try_promote_next
- **Commit:** 09c1e28

### notification-scheduler (Agent 6) -- Phase 2
- **Status:** COMPLETED
- **Files created:** 2 (app/scheduler/__init__.py, app/scheduler/jobs.py)
- **Issues encountered:** Wrong table name (registrations vs registrants)
- **Commit:** 3be1403

### public-registration-ui (Agent 7) -- Phase 3
- **Status:** COMPLETED
- **Files created:** 8 (frontend/package.json, server.js, app.js, middleware/flask-proxy.js, views/register.ejs, views/success.ejs, public/css/style.css, public/js/validation.js)
- **Issues encountered:** Proxy path stripping (FC28)
- **Commit:** 7adc8bf

### admin-ui (Agent 8) -- Phase 3
- **Status:** COMPLETED
- **Files created:** 5 (frontend/middleware/auth.js, routes/admin.js, views/admin/dashboard.ejs, views/admin/layout.ejs, public/js/admin-realtime.js)
- **Issues encountered:** Wrong stats field names, layout() helper not available, missing admin CSS
- **Commit:** f430b40

---

## FAILURES

### Contract Check -- get_registrant wrong kwarg (CRITICAL)
**Phase:** Assembly verification
**Severity:** CRITICAL
**Agent:** 3 (payment-webhooks)
**Error:** `get_registrant(conn, square_order_id=...)` -- function signature is `(conn, id)` with no kwargs
**Failure class:** FC2 (Type-Correct Spec, Wrong Usage)
**Resolution:** Replaced with direct SQL lookup by square_order_id

### Contract Check -- Wrong table name (CRITICAL)
**Phase:** Assembly verification
**Severity:** CRITICAL
**Agent:** 6 (notification-scheduler)
**Error:** `SELECT FROM registrations` -- table is named `registrants`
**Failure class:** FC1 (Naming Divergence)
**Resolution:** Changed to `registrants`

### Smoke Test -- Proxy path stripping
**Phase:** Smoke test
**Severity:** CRITICAL
**Agent:** 7 (public-registration-ui)
**Error:** Express strips `/api` prefix, Flask receives `/register` instead of `/api/register`
**Failure class:** FC28 (NEW -- Express Proxy Path Stripping)
**Resolution:** Changed to pathFilter approach

### Review -- Transaction safety (4 related P1s)
**Phase:** Review
**Severity:** CRITICAL
**Agents:** 1, 2, 5
**Error:** update_status() premature commit, try_promote_next premature commit, re-registration not atomic, stale capacity check
**Failure class:** FC29 (NEW -- No Transaction Boundary Prescription)
**Resolution:** Removed internal commits, deferred to callers, added BEGIN IMMEDIATE

### Review -- Admin dashboard broken (2 P1s)
**Phase:** Review
**Severity:** HIGH
**Agent:** 8 (admin-ui)
**Error:** renderStats reads wrong field names + Helmet CSP blocks scripts
**Failure class:** FC30 (NEW -- Response Field Name Mismatch)
**Resolution:** Fixed field names, configured CSP

---

## RUN_METRICS

### Final Build Metrics

| Metric | Value |
|--------|-------|
| Total agents | 8 |
| Total files | 35 |
| Total lines | ~1,750 |
| Total tests | 0 (not in scope) |
| Total commits | 15 (8 agent + 4 fix + 3 doc) |
| Spec consistency passes | 3 (7 contradictions fixed) |
| Contract check failures | 7 (all fixed) |
| Smoke test failures | 3 (all fixed) |
| P1 findings (review) | 8 |
| P2 findings (review) | 12 |
| P3 findings (review) | 8 |
| All P1s fixed | yes |
| All P2s fixed | no (8 remaining) |

### Agent Performance Summary

| Agent | Findings Caused | Failure Classes Hit | Notes |
|-------|----------------|--------------------|----|
| 1 (core) | 2 P2 | FC10 partial | errorhandler narrower than spec, limiter not exported |
| 2 (registration-admin) | 1 P1, 2 P2 | FC2, FC29 | Custom rate limiter, stale capacity check |
| 3 (payment-webhooks) | 2 CRITICAL, 1 P2 | FC2, FC1 | Wrong function signature, invented error code |
| 4 (email-engine) | 1 P2 | FC30 | Fabricated checkout URL |
| 5 (waitlist) | 1 P1, 1 P2 | FC29, FC3 | Premature commit, inline SQL |
| 6 (notification) | 1 CRITICAL | FC1 | Wrong table name (typo) |
| 7 (public-ui) | 1 CRITICAL | FC28 (new) | Proxy path stripping |
| 8 (admin-ui) | 1 P1, 2 P2 | FC30 (new) | Wrong stats field names, layout helper |

### Lessons for Next Build

1. FC28 (Express Proxy Path Stripping) -- new failure class for cross-stack builds
2. FC29 (Transaction Boundary Prescription) -- specs must say "does NOT commit"
3. FC30 (Response Field Name Mismatch) -- need "Consumer Reads" column in endpoint tables
4. Spec-consistency-checker catches mechanical mismatches that Codex misses -- run both
5. 8 parallel worktree agents with 0 merge conflicts validates cross-stack ownership boundaries
