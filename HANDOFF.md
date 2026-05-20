# HANDOFF -- Sandbox

**Date:** 2026-05-20
**Branch:** master
**Phase:** Ready for run 050 -- GigSheet (autopilot brainstorm + swarm build)

## Current State

VenueConnect (run 049) fully complete. All 9 deferred P2s resolved and committed. 18/18 smoke tests pass. Run 050 is scoped: **GigSheet** -- an outreach + booking pipeline platform for gigging musicians. This session conducted deep research across all solution docs, lessons learned, and agent pitfalls to design a build that fills ecosystem gaps and stress-tests 5+ untested swarm capabilities.

## Key Artifacts

| Artifact | Location |
|----------|----------|
| VenueConnect app | venueconnect/ |
| VenueConnect plan | docs/plans/2026-05-19-venueconnect-plan.md |
| VenueConnect solution doc | docs/solutions/2026-05-20-venueconnect-25-agent-swarm-build.md |
| Lead Scraper app | lead-scraper/ |
| Agent pitfalls (37 classes) | ~/.claude/docs/agent-pitfalls.md |
| Swarm spec patterns | ~/.claude/projects/-Users-alejandroguillen-Projects-sandbox/memory/patterns_swarm_spec.md |
| Workflow lessons | ~/.claude/projects/-Users-alejandroguillen-Projects-sandbox/memory/workflow_lessons.md |

## Run 050: GigSheet -- Outreach + Booking Pipeline

### What It Is

Musicians import leads (from Lead Scraper or manual entry), build email templates, send batch outreach to venues/promoters, track opens/responses, and convert replies into booking requests. "Mailchimp meets a CRM, built for gigging musicians."

### Why This Build

1. **Fills the ecosystem gap:** Lead Scraper finds contacts -> **GigSheet sends outreach + tracks pipeline** -> VenueConnect books shows -> Client Music Planner handles set lists
2. **Monetizable:** SaaS subscription ($29-79/mo tiers), pay-per-send overages, platform transaction fee on bookings created through outreach
3. **Pushes swarm to 30+ agents** -- biggest build yet
4. **Tests 5+ capabilities never tested in a swarm build:**
   - Background job queues (Celery/RQ for scheduled email sends)
   - Real-time updates (WebSocket/SSE for delivery tracking)
   - Third-party API integration (SendGrid/Mailgun OAuth)
   - File uploads & storage (press kits, logos, EPKs)
   - Multi-tenant data isolation (workspace per musician)

### Core Feature Set (brainstorm input)

- **Lead management:** Import CSV, manual add, Lead Scraper integration, tag/filter/segment
- **Template builder:** Rich email templates with merge fields (venue name, capacity, genre match), press kit attachment
- **Campaign engine:** Batch send with scheduling (timezone-aware), throttling, send-time optimization
- **Delivery tracking:** Open rates, click rates, bounce handling, response detection
- **Pipeline board:** Kanban-style outreach pipeline (contacted -> responded -> interested -> booking requested -> booked)
- **Booking bridge:** One-click "create booking request" that pushes to VenueConnect API (or standalone)
- **Analytics dashboard:** Campaign performance, conversion funnel, revenue attribution
- **Multi-tenant:** Workspace isolation, team invites, role-based access

### Stack Decision (carry forward from research)

- **Flask + SQLite + Jinja2** (same as VenueConnect -- proven at 25 agents)
- **Celery + Redis** for job queue (NEW -- untested in swarm)
- **SendGrid API** for email delivery (NEW -- untested)
- **WebSocket via Flask-SocketIO** or SSE for real-time updates (NEW -- untested)
- **File uploads via Flask** to local storage (NEW -- untested in swarm)

### Failure Patterns to Design Against

These are the top 5 from agent-pitfalls.md that MUST be addressed in the spec:

| FC | Pattern | Mitigation |
|----|---------|------------|
| FC1 | Naming divergence at ownership boundaries | Export Names Table in spec (exact field names, exact function names) |
| FC3 | Dead wiring / zero-caller exports | Pre-swarm completeness gate: every export must have a consumer |
| FC31 | Cross-flow data integrity across 3+ files | Flow-trace reviewer mandatory post-assembly |
| FC35 | IDOR role check without ownership verification | Coordinated Behaviors Table with prescriptive ownership checks |
| FC37 | Worktree commit failures (56% at 25 agents) | Orchestrator verifies `git log` per branch before assembly |

### Scale Target

- **30+ agents** (up from 25 in VenueConnect)
- **Vertical blueprint split** (validated pattern)
- **Shared modules:** db, auth, decorators, notifications, email_queue, file_storage
- **Cross-boundary surfaces:** email_queue <-> campaign engine, delivery tracking <-> WebSocket push, lead import <-> pipeline board, booking bridge <-> VenueConnect API

### Monetization Model

| Tier | Price | Includes |
|------|-------|----------|
| Solo | $29/mo | 500 emails/mo, 1 workspace, basic templates |
| Pro | $59/mo | 2,000 emails/mo, 3 workspaces, analytics, press kit hosting |
| Agency | $99/mo | 10,000 emails/mo, unlimited workspaces, team roles, API access |
| Overage | $0.01/email | Beyond tier limit |

## Deferred Items

### Run 049 (VenueConnect) -- ALL RESOLVED
- ~~049-D1 through 049-D9~~ All fixed in 3 batches (commits 0f7bd4b, 3b5747e, 841e463)

### Prior Runs
- 048-W1: create_event notes gap (MEDIUM, spec gap)
- 046-W1 ACCEPTED: No brute-force login protection. MEDIUM.
- 046-W2 ACCEPTED: Line-item parsing duplication. MEDIUM.

## Prompt for Next Session

```
Read HANDOFF.md. This is the Sandbox project, run 050 -- GigSheet.

Full autopilot run. Start with /workflows:brainstorm using the GigSheet
scope from HANDOFF.md (outreach + booking pipeline for musicians).
Target: 30+ agent swarm, Flask + SQLite + Celery + SendGrid + WebSocket.

Key context already researched:
- 5 untested capabilities: job queues, real-time, OAuth, file uploads, multi-tenant
- Top 5 failure patterns to design against: FC1, FC3, FC31, FC35, FC37
- Monetization: SaaS $29-99/mo tiers with per-send overages
- Ecosystem fit: Lead Scraper -> GigSheet -> VenueConnect -> Client Music Planner

Mandatory: inject all pitfalls from ~/.claude/docs/agent-pitfalls.md into
agent briefs. Copy autopilot tracking template to BUILD_TRACKING.md.
Run full compound loop: brainstorm -> plan -> spec convergence -> work -> review -> compound.
```
