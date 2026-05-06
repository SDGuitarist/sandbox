# Ethics Toolkit -- Handoff

## Current Phase: Cycle complete (build + review fixes)
## Next Phase: P2 cleanup or pre-workshop gate

## What Is This?
AI Filmmaking Ethics Platform -- 5 interactive tools for filmmakers navigating AI ethics: Disclosure Generator, Festival Policy Lookup, Project Risk Scanner, Provenance Chain Builder, Budget vs Ethics Calculator. Built with Next.js 15 + Supabase (Auth/Realtime/PostgreSQL) + Anthropic API + Square + Resend.

## Current State

15-agent 4-phase swarm build complete. All P0 (12 items) and P1 (16 items) review findings resolved across 3 commits. 18 commits total on master.

## What Was Built

| Phase | Scope |
|-------|-------|
| 1: Foundation | Next.js scaffold, Supabase schema + RLS, auth (anonymous + magic link), routing shell |
| 2.0: Pre-gate | Zod schemas + fixture tests for all 5 tools |
| 2: Tools | 5 deterministic tool engines + mock AI + Service Worker |
| 3: Realtime | Supabase Realtime, facilitator dashboard (5 widgets), attendee interaction components |
| 4: Integration | Anthropic API routes, Square checkout, Resend lifecycle emails, rate limiting |

## Review Fix Cycle (3 commits)

| Commit | Scope | Key Fixes |
|--------|-------|-----------|
| 524bfe2 | P0 (12 issues) | Import alias exports, atomic RPCs, dead wiring, AbortController timeouts |
| 5a95867 | P1 R1 (12 issues) | RLS tightening, HMAC tokens, FK cascades, cron concurrency guard |
| 2476db0 | P1 R2 (4 issues) | IF NOT EXISTS, validation shape standardization, useWorkshopChannel, AI route factory |

## Key Architectural Decisions

- **AI route factory** (`lib/ai/route-factory.ts`): 3 routes x ~20 lines of config instead of 3 x ~150 lines of boilerplate
- **Shared Realtime channel** (`lib/realtime/use-workshop-channel.ts`): 1 connection per dashboard, not 5
- **HMAC unsubscribe tokens** (`lib/email/send.ts`): `crypto.timingSafeEqual` verification
- **Atomic cron claims**: `UPDATE...WHERE status='pending'` as mutex

## Config Required

- `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ANTHROPIC_API_KEY` (falls back to mock mode if unavailable)
- `SQUARE_ACCESS_TOKEN` + `SQUARE_LOCATION_ID`
- `RESEND_API_KEY`
- `FACILITATOR_SESSION_SECRET`
- `UNSUBSCRIBE_SECRET` (for HMAC token signing)

## Known Deferred P2s

- 30+ `as any` casts (needs Supabase type generation)
- Missing security headers in `next.config.ts`
- Festival search LIKE wildcard escaping
- Service Worker cache never expires
- TypeScript types don't match SQL nullability
- No RLS INSERT policy for `workshop_sessions`

## Solution Docs

- [Swarm Build](../docs/solutions/2026-04-30-ethics-toolkit-platform-build.md) -- 15-agent build lessons
- [Review Fix Cycle](../docs/solutions/2026-05-06-ethics-toolkit-review-fix-cycle.md) -- P0/P1 fix patterns
- [Spec Convergence Loop](../docs/solutions/2026-04-30-spec-convergence-loop.md) -- spec hardening methodology

## Next Steps

1. Decide: P2 cleanup pass OR pre-workshop operational gate
2. If P2: prioritize `as any` casts (needs `supabase gen types`) and security headers
3. If operational: load test on Vercel, iPhone Safari + Android Chrome, projector setup
4. Post-launch: Square webhook automation, behavior-triggered email

## Prompt for Next Session

```
Read ethics-toolkit/HANDOFF.md for context. This is the AI Filmmaking Ethics Platform
at /Users/alejandroguillen/Projects/sandbox/ethics-toolkit.

Build is complete, all P0/P1 review findings resolved. Choose next action:
- P2 cleanup: run `npx supabase gen types` first, then fix `as any` casts
- Pre-workshop gate: load test, mobile browser testing, projector verification
```
