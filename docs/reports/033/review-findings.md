# Run 033: Ethics Toolkit -- Review Findings

**Date:** 2026-04-30
**Reviewers:** 5 parallel agents (Architecture, Security, Performance, Patterns, Data Integrity)
**Feed-Forward risk:** "Autopilot swarm at platform complexity -- cross-cutting concerns across 5 tools"

## Summary

| Priority | Count | Theme |
|----------|-------|-------|
| P0 | 12 | Broken imports, non-transactional claiming, race conditions, missing wiring, no timeouts |
| P1 | 16 | Inconsistent API shapes, missing rate limiting, FK cascades, mock duplication, UX divergence |
| P2 | 15 | Type safety, quote style, missing disclaimers, button styling, stale cache |

The swarm produced coherent architecture at the module level -- schemas, tool engines, and database types correctly implement the spec. **All failures are at integration seams** where one agent's output connects to another agent's input. This confirms the Feed-Forward risk.

---

## P0 -- Must Fix

### P0-1: Import name mismatches (13 files broken)
- `createBrowserClient` not exported from `client.ts` (7 files)
- `createServerClient` not exported from `server.ts` (3 files)
- `getOrCreateAnonymousSessionId` doesn't exist in `anonymous-session.ts` (3 files)
- **Root cause:** Agents agreed on interface contracts but not exact export names

### P0-2: Anonymous session claiming is NOT transactional
- `magic-link.ts` lines 21-51: two separate Supabase calls with no transaction
- If step 1 succeeds and step 2 fails, tool events are permanently orphaned
- **Fix:** Supabase RPC function wrapping both updates in BEGIN...COMMIT

### P0-3: Session claiming allows any user to claim any unclaimed session
- `save-results/route.ts`: anonymousSessionId from request body with no ownership check
- IDs visible in every realtime broadcast payload during workshops
- **Fix:** Tie anonymousSessionId to the magic link flow via signed parameter

### P0-4: Upvote counter race condition (non-atomic increment)
- `qna/upvote/route.ts` lines 112-125: read-then-write loses votes under concurrency
- **Fix:** PostgreSQL RPC function with atomic `upvote_count = upvote_count + 1`

### P0-5: Anthropic API calls have no timeout
- All 3 AI routes call `client.messages.create()` with no abort signal
- Stalls block users for up to 60 seconds (Vercel function timeout)
- **Fix:** AbortController with 15-second timeout, fallback to mock

### P0-6: Service Worker never registered
- `sw-register.ts` defined but never imported anywhere
- Entire offline degradation requirement is non-functional
- **Fix:** Import and call in attendee layout useEffect

### P0-7: `scheduleTrialEmails` never called
- Function exists at `schedule-trial-emails.ts` but imported nowhere
- No profile created on conversion, no trial started, no emails scheduled
- **Fix:** Wire into save-results route after session claiming

### P0-8: Rate limiting entirely unwired
- `withAiRateLimit` and all rate limit checkers defined but never imported by any route
- All rate limits from Section 9 are unenforced
- **Fix:** Wire middleware into AI, workshop, tool, and auth routes

### P0-9: `FACILITATOR_SESSION_SECRET` missing from .env.example
- Middleware and facilitator auth both read this env var
- Without it, facilitator routes redirect to login indefinitely

### P0-10: Inconsistent success response shapes
- Disclosure returns `{ deterministic, probabilistic }`
- Others return `{ deterministicPayload, probabilisticPayload }`
- Budget also includes `eventId` in response

### P0-11: Missing outer try/catch on disclosure and budget routes
- Uncaught errors return raw Next.js error pages instead of JSON

### P0-12: Two independent mock systems with divergent signatures
- Phase 2 mocks at `tools/*-mock.ts`, Phase 4 mocks at `ai/mock.ts`
- Budget mock returns `string` in Phase 2 vs `{ ethicalAnalysis: string }` in Phase 4

---

## P1 -- Should Fix

1. RLS too permissive -- anonymous can read ALL tool_events (`USING (true)`)
2. No rate limiting on facilitator login endpoint
3. Unsubscribe token is reversible base64 (not signed)
4. Seed migration not idempotent (no ON CONFLICT)
5. Schema migration not idempotent (no IF NOT EXISTS)
6. No ON DELETE behavior for several FKs (blocks 30-day cleanup)
7. Cron email processor has no concurrency guard
8. 60-second retry sleep exceeds Vercel function timeout
9. Triple definition of ToolType (enum + two union types)
10. Validation boundary inconsistency: `body` vs `body.input`
11. `ensureAnonymousSession` vs `getAnonymousSessionId` split
12. @react-pdf/renderer in client bundle (~500KB bloat)
13. Facilitator dashboard creates 5 separate Realtime channels
14. QnaList unsubscribes from parent channel on cleanup
15. AI route handler boilerplate duplicated 3 times
16. Budget mock returns string but route wraps in object

---

## P2 -- Nice to Have

1. 30+ `as any` casts on Supabase queries
2. Quote style inconsistency (single vs double)
3. Legal disclaimer missing from disclosure and festival pages
4. Submit button styling divergence
5. Inline type definitions instead of importing from schemas
6. No security headers in next.config.ts
7. Festival search doesn't escape LIKE wildcards
8. Q&A questionText has no max-length validation
9. topRiskDepartments array elements not validated as strings
10. In-memory rate limiter resets on cold start (accepted for v1)
11. SW cache never expires
12. next.config.ts has no performance configuration
13. TypeScript types don't match SQL nullability
14. Missing updated_at trigger
15. No RLS INSERT policy for workshop_sessions
