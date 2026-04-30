---
title: "AI Filmmaking Ethics Platform -- 15-Agent 4-Phase Swarm Build"
date: 2026-04-30
tags: [swarm, next.js, supabase, realtime, autopilot, platform, cross-cutting]
build_method: autopilot
agents: 15
phases: 4
files: 116
stack: Next.js 15, Supabase (Auth/Realtime/PostgreSQL), Anthropic API, Square, Resend
---

# AI Filmmaking Ethics Platform -- Swarm Build Solution Doc

## What Was Built

A 5-tool interactive ethics platform for filmmakers:
1. **AI Disclosure Generator** -- checklist + AI-generated disclosure statements
2. **Festival Policy Lookup** -- searchable database of 12 festival AI policies
3. **Project Risk Scanner** -- deterministic scoring engine (7-step formula) + AI recommendations
4. **AI Provenance Chain Builder** -- audit trail with PDF export
5. **Budget vs. Ethics Calculator** -- rate comparison + AI ethical analysis

Plus dual-mode workshop UX (anonymous attendee + facilitator), Supabase Realtime for 5 interaction types, Square checkout, Resend email lifecycle, and Service Worker offline caching.

## How It Was Built

15 agents across 4 sequential phases with integration gates:

| Phase | Agents | Scope |
|-------|--------|-------|
| 1: Foundation | 4 (scaffold, database, auth, ui-shell) | Next.js scaffold, Supabase schema, auth flows, routing shell |
| 2.0: Schemas | 1 (pre-gate) | Zod schemas + fixture tests for all 5 tools |
| 2: Tools | 3 (disclosure-festival, risk-provenance, budget-sw) | Deterministic tool logic + mock AI + Service Worker |
| 3: Realtime | 3 (realtime-engine, facilitator-dashboard, attendee-realtime) | Supabase Realtime, facilitator widgets, attendee components |
| 4: Integration | 3 (ai-routes, payments-email, rate-limiting) | Anthropic API, Square checkout, Resend emails, rate limiting |

## Risk Resolution

### Feed-Forward Risk: "Autopilot swarm at platform complexity"

**What was flagged:** Cross-cutting concerns (auth/entitlements, realtime sync, LLM integration, payment flow, email lifecycle) across 5 tools had never been tested at swarm scale. Previous builds were single-purpose apps.

**What actually happened:** The swarm produced coherent architecture at the module level -- schemas, tool engines, realtime types, and database types all correctly implemented the spec. **All failures were at integration seams** where one agent's output needed to connect to another agent's input.

Specific failures:
1. **Import name mismatches** (13 files broken): Agents agreed on interface contracts but not exact export names. The `database` agent exported `createClient`; auth/UI agents imported `createBrowserClient`. The `database` agent exported `createServiceClient`; auth agents imported `createServerClient`. Same pattern for `getOrCreateAnonymousSessionId` vs `ensureAnonymousSession`.

2. **Dead wiring** (2 critical functions never called): `scheduleTrialEmails` existed but no code called it. `registerServiceWorker` existed but no code imported it. The rate limiting middleware was complete but unwired into any route. The `payments-email` agent couldn't modify auth routes (ownership boundary), and the `auth` agent didn't know about email scheduling (built in a later phase).

3. **Race condition at integration boundary**: The upvote route used read-then-write because "Supabase JS v2 doesn't have a built-in atomic increment." The spec didn't prescribe an RPC function for this. The agent made a local decision that was correct for single-user testing but fails under workshop concurrency.

4. **Non-transactional cross-table operation**: Session claiming updated `anonymous_sessions` then `tool_events` as separate calls. The spec said "claim all data" but didn't prescribe a transaction. The agent implemented the happy path correctly but the failure path corrupts data.

**What was learned (the delta):**
- Shared specs must prescribe **exact export names** for shared modules, not just file names and function signatures.
- Functions that **cross ownership boundaries** (rate limiting wrapping AI routes, email scheduling called from auth) need explicit "wiring instructions" in the spec -- they can't be discovered by agents in isolation.
- Any **multi-row update** that must be atomic needs a prescribed PostgreSQL function in the spec. Agents will default to sequential Supabase JS calls.
- The **contract-check gate** catches mechanical errors (wrong file names, missing schemas) but does NOT catch design errors (race conditions, dead wiring, non-transactional operations). A "cross-boundary wiring check" gate is needed.

## Key Patterns (Reusable)

### 1. Compatibility Export Pattern
When swarm agents disagree on import names, add alias exports rather than renaming in all consumers:
```typescript
export function createClient() { ... }
export { createClient as createBrowserClient };
```
Smallest change, fixes all consumers.

### 2. PostgreSQL RPC for Atomic Operations
Any operation that increments a counter or updates multiple tables atomically:
```sql
CREATE OR REPLACE FUNCTION increment_upvote(p_question_id UUID)
RETURNS INTEGER AS $$
  UPDATE qna_questions SET upvote_count = upvote_count + 1
  WHERE id = p_question_id RETURNING upvote_count;
$$ LANGUAGE sql;
```
Call via `supabase.rpc('increment_upvote', { p_question_id: id })`.

### 3. AbortController Timeout for External API Calls
```typescript
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 15_000);
try {
  response = await client.messages.create({ ... }, { signal: controller.signal });
} finally {
  clearTimeout(timeout);
}
```
Falls back to mock mode on timeout instead of hanging for 60 seconds.

### 4. Phased Swarm with Schema Pre-Gate
Phase 2.0 (Zod schemas + fixture tests) runs before any tool agent starts. This ensures all tools share the same data contracts. Validated in this build: 5 tool agents produced compatible output because they all imported from the pre-validated schema module.

## Spec Improvements for Future Swarm Builds

1. **Export Name Table**: Add a table mapping file -> export name -> consuming files. Agents import exactly what the spec names.

2. **Cross-Boundary Wiring Section**: For each function that crosses ownership boundaries, specify: who creates it, who calls it, exact import path, when in the flow it's called.

3. **Atomic Operation Prescriptions**: Any multi-row update or counter increment gets a prescribed PostgreSQL RPC function in the database agent's assignment.

4. **Integration Wiring Gate**: After assembly merge, grep for all exported functions and verify each has at least one consumer. Dead exports at ownership boundaries are the #1 swarm failure mode.

## Deferred Items

- P1 issues from review (16 items): RLS tightening, seed idempotency, FK cascading, facilitator login rate limiting, unsubscribe token signing, mock deduplication, API shape standardization
- P2 issues from review (15 items): `as any` cleanup, security headers, quote style, button styling
- Pre-workshop gate: load test on Vercel, iPhone Safari + Android Chrome testing, projector setup
- Post-launch: Square webhook automation, behavior-triggered email, festival auto-scraping

## Feed-Forward

- **Hardest decision:** Fixing import mismatches with alias exports (add to source) vs updating all consumers (change 13 files). Chose alias exports -- smaller change, no risk of missing a consumer.
- **Rejected alternatives:** Rerunning the swarm with corrected spec (too expensive, build is mostly correct), manual review without agents (slower, less thorough).
- **Least confident:** The P1 items deferred -- especially RLS being too permissive (`USING (true)` on tool_events for anonymous users) and the unsigned unsubscribe token. These need fixing before any real user data flows through.
