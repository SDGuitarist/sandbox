---
title: "Workshop Registration Hub -- 8-Agent Cross-Stack Swarm Build"
date: 2026-05-13
type: swarm-build
tags: [flask, express, sqlite, supabase, square, resend, cross-stack, swarm]
agents: 8
findings_pre_review: 10
findings_review: 30
p1_fixed: 8
p2_fixed: 4
---

# Workshop Registration Hub -- 8-Agent Cross-Stack Swarm Build

## What Was Built

A workshop registration system for the Amplify AI May 30 workshop. Flask backend with SQLite, Express frontend with EJS templates, Supabase realtime for admin live updates. Square Payment Links for checkout, Resend for transactional email. 35 files, ~1,750 lines across 8 swarm agents.

## Key Technical Decisions

1. **Express proxies all API calls to Flask** -- browser never talks directly to Flask. Eliminates CORS/CSRF cross-stack issues.
2. **SQLite is source of truth, Supabase is read-optimized mirror** -- non-PII columns only in Supabase, full data from Flask API.
3. **Supabase realtime is change signal only** -- admin dashboard refetches full data from Flask on each event, never renders Supabase payload.
4. **Square Payment Links API** -- `quick_pay` pattern, not deprecated CreateCheckout.

## What Went Wrong (Pre-Review Pipeline)

### Spec Consistency Gate: 7 contradictions in 3 passes

The spec had been through 4 Codex convergence passes with 0 P0s, but the automated spec-consistency-checker still found 7 contradictions:

| Pass | Contradictions | Examples |
|------|---------------|----------|
| 1st | 5 FAIL | Admin stats "pending" vs "pending_payment", create_checkout_link "Agent 2 only" but Agent 5 needs it, try_promote_next missing from Export Names Table |
| 2nd | 2 FAIL | try_promote_next return type mismatch, Agent 3 brief says "mark paid on refund" (impossible) |
| 3rd | 0 FAIL | PASS |

**Lesson:** Codex reviews find high-level design contradictions. The spec-consistency-checker finds mechanical mismatches (field names, return types, cross-table references). Both are needed -- they catch different failure classes.

### Contract Check: 7 failures (2 critical runtime crashes)

| Finding | Severity | Root Cause |
|---------|----------|------------|
| `get_registrant(conn, square_order_id=...)` -- wrong function signature | CRITICAL | Agent 3 invented a keyword arg that doesn't exist |
| Scheduler queries `registrations` table (should be `registrants`) | CRITICAL | Agent 6 typo in table name |
| Non-spec error code `INVALID_SIGNATURE` | P2 | Agent 3 invented an error code |
| `errorhandler(500)` not `errorhandler(Exception)` | P2 | Agent 1 used a narrower handler |
| `get_next_waitlisted` not used in waitlist/routes.py | P2 | Agent 5 used inline SQL instead of model function |
| Admin routes missing WWW-Authenticate header | P2 | Agent 2 forgot the header |
| flask-limiter not applied to routes | P2 | Agent 2 built custom rate limiter instead of using the prescribed one |

**Lesson:** FC2 (Type-Correct Spec, Wrong Usage) struck again -- Agent 3 assumed `get_registrant` had a `square_order_id` kwarg. The spec had the correct signature but the agent invented a calling convention. Adding usage examples to every model function helps but doesn't fully prevent this.

### Smoke Test: 3 P0 bugs

| Bug | Root Cause |
|-----|------------|
| Express proxy strips `/api` prefix | `app.use('/api', flaskProxy)` makes Express strip the mount path. Fixed with `pathFilter` option. |
| Admin dashboard `layout()` undefined | Agent 8 used `express-ejs-layouts` syntax but package isn't installed. Fixed by making dashboard self-contained. |
| Square API error crashes registration | `create_checkout_link` not wrapped in try/except. Fixed with error handling. |

**Lesson:** The proxy path stripping is a new failure class specific to cross-stack builds. When Express mounts middleware at a path, it strips that path. If the backend expects the full path, the proxy must use `pathFilter` instead of mount-point routing.

## What Went Wrong (Review Phase)

### P1 Findings: 8 total (4 transaction safety, 2 dashboard, 1 security, 1 performance)

The four transaction safety issues were the most severe:

1. **`update_status()` commits prematurely** -- every caller lost transaction control
2. **`try_promote_next()` commits before checkout link** -- Square failure strands registrant
3. **Re-registration path not atomic** -- last-seat race on re-register
4. **Stale capacity check** -- `get_paid_count()` disagrees with `register_attendee()` internal check

**Root cause:** The spec prescribed the `register_attendee` function with `BEGIN IMMEDIATE` but didn't prescribe transaction boundaries for other operations. Agents defaulted to "commit after every write" which is safe in isolation but breaks multi-step flows.

**Lesson (NEW):** Specs must prescribe transaction boundaries, not just atomic operations. If a function is called inside a larger transaction, the spec must say "does NOT commit -- caller commits." The absence of transaction guidance causes agents to default to commit-per-write.

### Cross-Stack Contract Gaps (Feed-Forward Risk Materialized)

The Feed-Forward risk was "cross-stack API contract between Flask and Express is novel." This materialized in:
- Admin dashboard `renderStats()` reads `data.paid` but Flask returns `data.paid_count`
- Dashboard reads `data.pending` but Flask returns `data.pending_payment`
- Helmet default CSP blocks CDN scripts and inline JS on admin dashboard
- Fabricated checkout URLs in email engine (`amplifyai.to/checkout/` doesn't exist)

**Lesson:** Cross-stack field name contracts need a response schema section in the spec, not just endpoint tables. The endpoint table says "returns JSON" but doesn't prescribe exact field names that the consumer reads. Adding a "Consumer Reads" column to the endpoint table would catch these.

## Risk Resolution (Feed-Forward Chain Closure)

1. **What was flagged:** Cross-stack API contract between Flask and Express
2. **What actually happened:** 5 cross-stack contract gaps found (proxy path, stats field names, CSP, checkout URLs, layout helper). The proxy path was the most surprising -- it's an Express framework behavior, not a spec issue.
3. **What was learned:** Cross-stack builds need THREE contract verification surfaces: (a) endpoint paths, (b) response field names consumed by the frontend, (c) middleware/framework behaviors (CSP, proxying, body parsing order). The spec covered (a) thoroughly, partially covered (c) in middleware ordering, but missed (b) entirely.

## New Failure Classes Discovered

### FC-NEW-1: Express Proxy Path Stripping
When Express mounts middleware at a path (`app.use('/api', proxy)`), it strips that prefix before passing to the middleware. If the backend expects the full path, the proxy silently drops it. Use `pathFilter` in the proxy config instead.

### FC-NEW-2: Spec Prescribes Atomic Operation but Not Transaction Boundary
Spec says "use BEGIN IMMEDIATE for capacity check" but doesn't say "update_status does NOT commit." Agents default to commit-per-write, which breaks multi-step flows that the spec author assumed would be transactional.

### FC-NEW-3: Cross-Stack Response Field Name Mismatch
Backend returns `paid_count`, frontend reads `paid`. Endpoint tables specify response shapes but not the exact field names that the consumer destructures. Need a "Consumer Reads" column.

## Agent Performance

| Agent | Role | Findings Caused | Notes |
|-------|------|----------------|-------|
| 1 (core) | Foundation | 2 | errorhandler(500) instead of Exception, flask-limiter not accessible |
| 2 (registration-admin) | API routes | 3 | Custom rate limiter, missing WWW-Authenticate, stale capacity check |
| 3 (payment-webhooks) | Webhooks | 3 | Wrong function signature (FC2), invented error code, invented kwarg |
| 4 (email-engine) | Email | 1 | Fabricated checkout URL |
| 5 (waitlist) | Promotion | 1 | Inline SQL instead of model function, premature commit |
| 6 (notification) | Scheduler | 1 | Wrong table name (typo) |
| 7 (public-ui) | Express frontend | 1 | Proxy path stripping (framework behavior) |
| 8 (admin-ui) | Admin dashboard | 3 | Wrong stats field names, layout() helper, missing admin CSS |

## Verification Pipeline Results

| Gate | Status | Issues Found | Fixed |
|------|--------|-------------|-------|
| Spec consistency (3 passes) | PASS | 7 contradictions | All 7 |
| Ownership gate | PASS | 0 violations | -- |
| Assembly merge (8 branches) | PASS | 0 conflicts | -- |
| Contract check | FAIL -> PASS | 7 mismatches | All 7 |
| Smoke test | FAIL -> PASS | 3 P0 bugs | All 3 |
| Review (4 agents) | Complete | 8 P1, 12 P2, 8 P3 | 8 P1, 4 P2 |

## Feed-Forward

- **Hardest decision:** Whether to run Agent 9 (integration-wiring) in a worktree or defer to post-assembly. Deferred -- the spec-contract-checker and assembly-fix agents served the same purpose.
- **Rejected alternatives:** Running agents in phased order (1, then 2-6, then 7-8) -- launched all 8 in parallel since worktrees provide isolation.
- **Least confident:** The transaction boundary fixes. Removing `conn.commit()` from `update_status()` changes the contract for ALL callers. If any caller forgot to add their own commit, data silently stays uncommitted until connection close.
