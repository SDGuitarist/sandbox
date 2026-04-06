---
title: Marketing Funnel App
origin: conversation
date: 2026-03-30
origin_repo: sandbox-auto
origin_context: "7-service chain reaction architecture design. See sandbox-auto repo for implementation (planned, not built)."
---

# Marketing Funnel App — Brainstorm

## What We're Building

A complete multi-channel marketing funnel with 7 event-driven services connected via Supabase Realtime chain reactions. The app handles the full lifecycle: landing page with A/B variants, lead capture, lead scoring, mock email drip sequences, mock webhook/SMS delivery, campaign management, and a realtime admin dashboard.

This is the most complex build in sandbox-auto — designed to exercise every compound engineering pattern from prior cycles at maximum scale.

## Why This Approach

**Chain Reaction Architecture** was chosen over monolith or hub-and-spoke because:
- Exercises the most learnings: shared specs across 7 services, data ownership contracts, Realtime subscriptions, SSRF protection, chain reaction coordination
- Each service owns one responsibility and triggers the next via Supabase writes — matching the pattern proven in Uptime Pulse's incident pipeline
- Event-driven design means services are independently testable and deployable
- Rejected: Monolith (doesn't exercise multi-service coordination), Hub-and-spoke (single point of failure, no event-driven patterns)

## The 7 Services

| # | Service | Type | Deploys To | Owns |
|---|---------|------|-----------|------|
| 1 | Landing Page | Static frontend | GitHub Pages | A/B variant display, form UI |
| 2 | Funnel API | Express server | Railway | Lead intake, validation, variant assignment, writes to Supabase |
| 3 | Lead Scorer | Worker process | Railway | Scores leads based on actions, updates lead records |
| 4 | Email Service | Worker process | Railway | Mock email sends, drip sequence scheduling |
| 5 | Webhook Service | Worker process | Railway | Mock outbound webhooks (Slack, CRM, SMS) |
| 6 | Campaign Manager | Worker process | Railway | Campaign config (variants, rules), conversion tracking via Realtime |
| 7 | Admin Dashboard | Static frontend | GitHub Pages | Realtime metrics, funnel visualization, campaign controls |

## Chain Reaction Flow

```
User visits Landing Page
  → Landing Page calls Funnel API for A/B variant (synchronous HTTP — the one exception to event-driven)
  → User fills form
  → Funnel API validates + writes lead to Supabase
  → Lead Scorer detects new lead (Realtime) → scores + updates lead
  → Email Service detects scored lead (Realtime) → schedules drip sequence
  → Webhook Service detects scored lead (Realtime) → fires mock webhooks
  → Admin Dashboard shows all events in realtime
```

Most arrows are Supabase Realtime subscriptions. The one exception: variant assignment is a synchronous API call (the Landing Page needs a variant before the user does anything). All post-submission processing is event-driven through the database.

## Key Decisions

1. **All integrations are mocked** — No real email/SMS/webhook services. Mock services log to Supabase tables instead of sending. Safe for sandbox, still exercises the full async chain.
2. **A/B testing built in** — Funnel API assigns variants using campaign rules stored in Supabase (written by Campaign Manager). Conversion = form submission. Campaign Manager tracks conversion rates per variant via Realtime.
3. **Lead scoring included** — Leads scored based on form data (fields filled, source, variant). No separate page-view tracking layer — keep scope to form submissions only.
4. **Event-driven, with one exception** — Post-submission processing is all Realtime. The one synchronous call is variant assignment (Landing Page → Funnel API) because it must happen before the user acts.
5. **Shared spec is mandatory** — Every service boundary (API shapes, DB schema, CSS classes, env vars) defined in the plan before any code. Prior cycles proved 0 mismatches with spec vs 7 without.
6. **Data ownership is explicit** — Each table has exactly one writer service. Learned from chain reaction solution doc where duplicate writes caused bugs.
7. **Best-effort, no retries** — If a worker fails mid-chain, the lead stays in its current state. No retry queue or dead-letter handling in sandbox. Workers log errors to an `events` table for dashboard visibility.

## Learnings This Exercises

| Learning | Source | How It Applies |
|----------|--------|---------------|
| Shared interface spec | swarm-build-alignment solution | 7 services need a contract — largest test yet |
| Data ownership contracts | chain-reaction solution | Each table owned by one service, no duplicate writes |
| SSRF protection | uptime-pulse solution | Webhook service fetches URLs — needs DNS blocklist |
| Chain reactions | chain-reaction solution | 5-step event chain through Realtime |
| Adaptive backoff | research-agent solution | Email/webhook batching with rate limit handling |
| Deploy order | uptime-pulse plan | DB → API → Workers → Frontends |
| RLS patterns | uptime-pulse migrations | Public read, service-key write |
| XSS/input validation | review findings | Form inputs on landing page |
| Config validation at startup | review findings | 4 Railway services need env var checks |
| Timing-safe secret comparison | review findings | Cron secrets on worker endpoints |

## Resolved Questions

1. **Worker architecture:** Separate Railway services — each worker gets its own Dockerfile and deploy. More realistic, exercises deploy coordination across 4+ services. Workers are long-running processes that subscribe to Supabase Realtime (not cron-triggered).
2. **Realtime fan-out:** Independent subscribers — each service subscribes to Realtime on its own. One failing doesn't block others. Matches real-world event-driven systems.
3. **Dashboard scope:** Both raw event logs (live stream) AND aggregated funnel metrics (conversion rates, avg lead score, A/B test comparisons).

## Feed-Forward

- **Hardest decision:** Chain reaction vs hub-and-spoke. Chain reaction is harder to debug but exercises more learnings — the whole point of this sandbox.
- **Rejected alternatives:** Monolith API (doesn't test multi-service), hub-and-spoke (single point of failure), real email integration (requires secrets in sandbox).
- **Least confident:** Whether 4 independent Realtime subscribers reacting to the same event will cause race conditions or duplicate processing. The Uptime Pulse incident pipeline had 5 services but they were sequential — this is parallel fan-out, which is untested.
