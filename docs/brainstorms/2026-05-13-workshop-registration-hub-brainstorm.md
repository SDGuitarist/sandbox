# Workshop Registration Hub -- Brainstorm

**Date:** 2026-05-13
**Use case:** Amplify AI May 30 workshop registration system
**Real goal:** Push swarm agent coordination to new limits -- most ambitious build to date

## What We're Building

A workshop registration system with:
- Public registration form with Square payment integration
- Admin dashboard with live registrant tracking
- Email automation (confirmation, reminders, post-workshop follow-up)
- Waitlist with FIFO queue when capacity (35 seats) is reached
- Payment webhook handling for automated status updates

**Dual purpose:** The workshop use case is real (May 30 Amplify AI workshop at Expressive Arts San Diego, $175/seat). But the primary goal is stress-testing the swarm autopilot with the hardest coordination challenge yet.

## Why This Is a Stress Test

This build introduces FOUR new integration surfaces that no prior swarm build has attempted:

| New Surface | Why It's Hard | Prior Builds |
|-------------|---------------|--------------|
| **Cross-stack (Flask + Express)** | Two spec templates, cross-language API contract | All prior builds were single-stack |
| **Two data stores (SQLite + Supabase)** | Data ownership across stores, sync boundaries | Prior builds used one DB |
| **Real external APIs (Square + Resend)** | Sandbox keys, real signatures, webhook verification | Prior builds were internal-only |
| **Event-driven chains** | Payment -> email -> waitlist -> dashboard (4+ agents must agree on event contract) | Prior builds had simple request/response |

## Data Flow

SQLite is the source of truth. All writes go through Flask. Supabase is a read-optimized mirror for admin realtime features.

```
Registrant submits form
  -> Express frontend POSTs to Flask API
    -> Flask writes to SQLite
    -> Flask calls sync function (Agent 1) to push row to Supabase
    -> Flask returns response to Express

Square sends payment webhook
  -> Flask receives, verifies signature, updates SQLite
  -> Flask calls sync function to update Supabase row
  -> Flask triggers email confirmation via Email Engine

Admin opens dashboard
  -> Express server-renders page with data from Flask API (initial load)
  -> Supabase realtime subscription pushes live updates (new registrations, payment status changes)
```

**Single sync point:** Agent 1 (Core + DB) owns the sync function. No other agent writes to Supabase directly. This prevents dual-write inconsistencies and keeps data ownership clean.

**Error boundaries:** Errors at sync boundaries (Supabase down, Resend 429) are logged and retried by the owning agent. Flask never blocks a response waiting for sync or email -- these are fire-and-forget with retry.

## Architecture: Clean Backend/Frontend Split

**Approach chosen:** Two teams separated by stack, connected by a cross-stack API contract. Research from 11 prior swarm builds confirmed:
- "One agent, one job" -- feature verticals (one agent doing both Python + JS) violate this rule
- "Vertical file ownership" -- Flask agents own .py, Express agents own .js, zero overlap
- "Integration Wiring Agent" -- mandatory here because this is the first cross-stack build (FC22: nobody has wired Flask + Express in a swarm before)
- Flask and Express run as separate processes (different ports). CORS configuration owned by Agent 1.

### Agent Lineup (9 agents)

#### Flask Backend Team (6 agents)

| # | Agent | Responsibility | Key Files |
|---|-------|---------------|-----------|
| 1 | Core + DB + Models | SQLite schema, models, app factory, Supabase sync function, CORS config | run.py, app/__init__.py, db.py, models.py, schema.sql, supabase_sync.py |
| 2 | Registration API | Form intake, validation, duplicate detection, capacity check, CSV export endpoint | app/registration/ blueprint |
| 3 | Payment Webhooks | Square signature verification, idempotent status updates | app/payments/ blueprint |
| 4 | Email Engine | Resend integration, 4 template types (confirmation, 7d reminder, 1d reminder, post-workshop). Owns HOW to send (template selection, Resend API call). | app/email/ module |
| 5 | Waitlist + Capacity | FIFO queue, auto-promote when spot opens, trigger email on promotion | app/waitlist/ blueprint |
| 6 | Notification Scheduler | Cron-based reminder dispatch, idempotency keys, timezone handling. Owns WHEN and WHO to send (query registrants, check schedule, call Email Engine). | app/scheduler/ module |

#### Express Frontend Team (2 agents, EJS templates)

| # | Agent | Responsibility | Key Files |
|---|-------|---------------|-----------|
| 7 | Public Registration Page | Form UI, client-side validation, Square checkout redirect, mobile-first | public/register/ |
| 8 | Admin UI | Server-rendered (EJS) admin dashboard: registrant table, payment status, capacity meter, registration funnel stats, CSV download. Basic auth (password from env var). Supabase realtime subscription (anon key, read-only RLS) for live updates. All data fetched from Flask API. | public/admin/ |

#### Integration (1 agent)

| # | Agent | Responsibility |
|---|-------|---------------|
| 9 | Wiring Agent | Connect all pieces post-assembly: imports, route registration, cross-stack API verification, smoke test |

### Spec Documents (3)

1. **Flask shared spec** -- from existing `docs/templates/shared-spec-flask.md` template
2. **Node shared spec** -- from existing `docs/templates/shared-spec-node.md` template
3. **Cross-stack API contract** -- NEW document defining exact Flask API endpoints that Express frontend consumes (request/response shapes, auth headers, error formats)

## Key Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Architecture | Clean backend/frontend split | Research: one-agent-one-job rule + vertical file ownership |
| Agent count | 9 | 6 backend + 2 frontend + 1 integration wiring (first cross-stack build, FC22) |
| Frontend stack | Express (Node) | Hardest cross-stack test; proven Node spec template exists |
| External APIs | Real APIs with sandbox keys | Square sandbox mode + Resend test mode; most production-realistic |
| Database | SQLite (backend) + Supabase (frontend realtime) | Tests two-data-store coordination; both patterns proven individually |
| Waitlist logic | FIFO (first come, first served) | Simple, fair, easy to explain; YAGNI on priority tiers |
| Realtime visibility | Admin-only | Simpler RLS policies; public doesn't see seat count |
| Workshop capacity | 35 seats | Mid-range of 30-40 target; clear number for capacity logic |
| Spec convergence | Full loop (Codex + human verification) | Novel cross-stack API contract has never been tested -- convergence loop must scrutinize it |

## What Must Not Change

- Existing sandbox apps must not be modified
- Global CLAUDE.md and agent-pitfalls.md are read-only during build (updated only during compound phase)
- Shared spec templates in docs/templates/ are references, not modified
- Production DB safety rules always apply (copy to /tmp for testing)

## Existing Resources to Leverage

From sandbox knowledge base:
- **Email patterns:** ethics-toolkit Resend integration with retry logic, HMAC-signed tokens
- **Payment patterns:** ethics-toolkit Square checkout, entitlement lifecycle
- **Webhook patterns:** webhook-delivery app exponential backoff, atomic claiming
- **DB patterns:** lead-scraper SQLite WAL mode, context managers, migration safety
- **Auth patterns:** ethics-toolkit magic link, anonymous sessions
- **Spec templates:** docs/templates/shared-spec-flask.md, shared-spec-node.md

From amplify-workshop:
- Workshop details: May 30, Expressive Arts San Diego, $175, 10am-2pm
- Registration fields: Name, Email, Role (Writer, Director, Composer, Post-Production, Student, Other)
- Square merchant ID: N34QM28N0MHKJ
- Existing intake email template: playbook/registrant-intake-email.md

## Success Criteria (Swarm Test)

This build succeeds as a stress test if:

1. **Zero structural failures** at assembly (no FC22 integration wiring gaps)
2. **Cross-stack API contract holds** -- Express frontend successfully calls Flask API with zero endpoint mismatches
3. **Two data stores coexist** -- SQLite is source of truth, Supabase realtime works for admin dashboard
4. **Event-driven chains work** -- payment webhook -> email confirmation -> waitlist promotion -> dashboard update all trigger correctly
5. **Spec convergence loop catches cross-section contradictions** before autopilot launches
6. **All 23 failure classes injected** into agent briefs; post-review traces findings back to agents

The build succeeds as a workshop tool if:
- A registrant can fill out a form, pay via Square, receive a confirmation email
- Admin can see all registrants, payment status, and export CSV
- Waitlist activates when capacity is reached

## Resolved Questions

1. **Supabase project:** Create a new project. Clean room for the experiment -- no risk to ethics-toolkit data, easy teardown if build fails.
2. **Square sandbox keys:** Need to set up before build. Square has a sandbox mode -- create credentials as pre-build setup.
3. **Resend API key:** Defer to plan phase -- check if ethics-toolkit key is reusable or create new one during setup.
4. **Deployment target:** Local only. Pure stress test -- no deployment distraction. If the build works well, Railway deployment is a separate effort.

## Feed-Forward

- **Hardest decision:** Cross-stack split (Flask + Express) instead of single-stack. Research supports it, but this is genuinely untested territory for the swarm. If the API contract has gaps, both teams build against wrong assumptions.
- **Rejected alternatives:** Feature verticals (one agent per feature across both stacks) -- violates one-agent-one-job rule. Jinja2 + HTMX -- safer but doesn't test cross-stack coordination. Layer cake -- blurry ownership, worst of all options.
- **Least confident:** The cross-stack API contract document. We have Flask and Node spec templates, but the bridge between them is new. This is where P0 cross-section contradictions are most likely to hide. The spec convergence loop (Codex + human verification) must scrutinize this document hardest.
