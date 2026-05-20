---
title: GigSheet -- Outreach + Booking Pipeline for Musicians
date: 2026-05-20
status: complete
run: "050"
feed_forward:
  risk: "SQLite job queue + SSE at 31-agent scale with cross-boundary email flow (queue → sender → webhook → SSE push) is the longest data chain ever attempted"
  verify_first: true
---

# GigSheet Brainstorm

## What We're Building

An outreach and booking pipeline platform for gigging musicians. Musicians import venue/promoter leads, build email templates with merge fields, send batch outreach campaigns, track delivery (opens/clicks/bounces), manage a kanban pipeline from first contact through booking, and view analytics on conversion rates.

**Target user:** Solo musician or small band managing their own booking outreach.

**Core value proposition:** "Mailchimp meets a CRM, built for gigging musicians." One tool to find leads, send personalized outreach, and track the pipeline from cold email to confirmed gig.

**Ecosystem position:** Lead Scraper finds contacts → **GigSheet sends outreach + tracks pipeline** → VenueConnect books shows → Client Music Planner handles set lists.

## Why This Approach

### Approach Considered: Full-Stack with Celery + Redis + WebSocket
- Pros: Industry standard, battle-tested at scale, real concurrency
- Cons: Two extra infrastructure dependencies (Redis, Celery worker), never tested in swarm, dramatically increases agent count for infrastructure wiring
- **Rejected:** Too much infrastructure risk for an MVP. The job-queue-system solution doc proves SQLite queues work for this scale.

### Approach Chosen: Flask + SQLite + SSE (Zero New Infrastructure)
- Pros: Proven stack at 25-agent scale, SQLite job queue pattern documented with known pitfalls, SSE is simpler than WebSocket for one-way updates, no Redis/Celery worker process
- Cons: Won't scale beyond ~100 concurrent sends without WAL contention, SSE doesn't support client→server messages
- **Why this wins:** MVP needs to demonstrate the product, not handle production load. SQLite job queue handles the "async email send" requirement. SSE handles "show send progress." Both are proven patterns with documented pitfalls.

### Approach Considered: Serverless (Vercel + Supabase)
- Pros: No server management, built-in real-time
- Cons: Wrong ecosystem (sandbox uses Flask), no SQLite, different swarm patterns
- **Rejected:** Doesn't match sandbox standard stack.

## Key Decisions

### 1. SQLite Job Queue (NOT Celery/Redis)
Background email sends use a `job_queue` table with atomic claim pattern:
```sql
UPDATE job_queue SET status='running', worker_id=?, claimed_at=datetime('now')
WHERE id = (SELECT id FROM job_queue WHERE status='pending' AND scheduled_at <= datetime('now') ORDER BY created_at LIMIT 1)
```
Check `cursor.rowcount == 1` before processing. Timeout detection: if `claimed_at` is older than 5 minutes and status is still 'running', reclaim as 'pending'.

A separate `send_worker.py` process polls the queue every 2 seconds. NOT run inside the Flask process.

**Lesson applied:** From job-queue-system -- compute next_run_at INSIDE transaction, fetch by specific id not worker_id.

### 2. SSE for Real-Time Updates (NOT WebSocket)
Campaign send progress uses Server-Sent Events (SSE). The campaign send page opens an EventSource connection to `/api/campaigns/<id>/progress`. The job worker updates a `campaign_progress` table row. The SSE endpoint polls that row every 1 second and streams JSON events:
```
event: progress
data: {"sent": 45, "total": 100, "failed": 2, "status": "sending"}
```

**Why not WebSocket:** We only need server→client (one-way). SSE is native browser API, no Flask-SocketIO dependency, simpler for agents to implement.

### 3. SendGrid Mock Mode
A `sendgrid_client.py` module with two implementations behind a config flag:
- `SENDGRID_MODE=mock` (default): Logs to `email_sends` table, simulates delivery webhook after 2-second delay
- `SENDGRID_MODE=live`: Calls SendGrid v3 API with real API key

Both implementations expose the same interface: `send_email(to, from_email, subject, html_body, tracking_id) -> dict`. Mock mode returns `{"status": "accepted", "message_id": "mock-<uuid>"}`.

### 4. Multi-Tenant via workspace_id Column
Every tenant-scoped table includes `workspace_id INTEGER NOT NULL REFERENCES workspaces(id)`. Every query in every route includes `WHERE workspace_id = ?` using `g.workspace['id']` set by `@require_workspace` decorator.

**No separate databases.** No row-level security. Just consistent column filtering.

### 5. Pipeline Stages as Fixed Enum
Pipeline stages are NOT user-customizable for MVP:
```python
PIPELINE_STAGES = ['new', 'contacted', 'responded', 'interested', 'booking_requested', 'booked', 'declined']
```
Each lead has a `pipeline_stage` column. The kanban board shows one column per stage. Drag-drop moves call `POST /leads/<id>/move` with `{"stage": "responded"}`.

### 6. Merge Fields as Simple {{variable}} Syntax
Email templates use `{{venue_name}}`, `{{contact_name}}`, `{{capacity}}`, `{{genre}}` etc. Rendering uses Python `str.replace()` with the lead's data dict. No Jinja2 in templates (too dangerous with user content).

Available merge fields are defined in the spec. Template preview substitutes sample data.

### 7. File Uploads to Local Storage
Press kits, logos, EPKs upload to `uploads/<workspace_id>/<uuid>.<ext>`. Served via Flask route `/files/<file_id>` with workspace ownership check. PIL for image thumbnails (logos). PDF and ZIP pass-through (no processing).

**Security:** BLOCKED_EXTENSIONS = {'.exe', '.bat', '.sh', '.cmd', '.ps1', '.scr'}. PIL MAX_IMAGE_PIXELS = 50_000_000 set at module import. Filename NFKC normalization + null byte strip.

### 8. Money as Integer Cents
All financial values (campaign budgets, per-send costs, overage charges) stored as integer cents. Display via `|dollars` Jinja filter. Form inputs accept dollar strings, convert: `int(round(float(value) * 100))`.

### 9. Agent Scale: 31 Agents
Vertical blueprint split. Each agent owns a Flask blueprint + templates + static.

**Shared modules (4 agents):**
1. scaffold -- app factory, config, base templates, CSS/JS, requirements.txt
2. auth -- login, register, logout, workspace creation/selection
3. models -- all model functions, schema.sql, db.py
4. decorators -- @login_required, @require_workspace, @require_role, rate limiting

**Lead management (4 agents):**
5. lead-list -- lead listing with pagination, search (FTS5), filter by tag/stage
6. lead-crud -- create, read, update, delete individual leads
7. lead-import -- CSV upload, preview, validation, commit to DB
8. lead-tags -- tag CRUD, lead-tag assignments, segment definitions

**Templates (3 agents):**
9. template-list -- template listing and management
10. template-editor -- create/edit templates with merge field insertion
11. template-preview -- render preview with sample data, test send single email

**Campaigns (4 agents):**
12. campaign-list -- campaign listing with status filters
13. campaign-editor -- create/edit campaign, select recipients, choose template
14. campaign-sender -- enqueue batch send jobs, throttling config
15. campaign-scheduler -- timezone-aware scheduling, recurring campaign support

**Delivery & tracking (3 agents):**
16. delivery-webhooks -- SendGrid inbound webhook handler (open/click/bounce/delivered)
17. delivery-stats -- aggregate delivery metrics per campaign, per lead
18. delivery-dashboard -- campaign performance charts, delivery timeline

**Pipeline (3 agents):**
19. pipeline-board -- kanban view with drag-drop (SortableJS), stage columns
20. pipeline-actions -- stage transitions, bulk moves, add notes to leads
21. pipeline-detail -- lead detail view within pipeline context, activity history

**Analytics (2 agents):**
22. analytics-overview -- workspace-level stats, conversion funnel, top campaigns
23. analytics-campaigns -- per-campaign deep dive, A/B comparison (future)

**Workspace & team (2 agents):**
24. workspace-settings -- workspace name, branding, email defaults, quota display
25. workspace-members -- invite members, assign roles (owner/admin/member), remove

**Infrastructure (4 agents):**
26. email-queue -- SQLite job queue processor (send_worker.py), claim/execute/update
27. sendgrid-client -- SendGrid API wrapper, mock mode, webhook verification
28. file-uploads -- upload handler, file serving, thumbnail generation
29. sse-events -- SSE endpoint for campaign progress, notification stream

**Support (2 agents):**
30. seed -- demo workspace with leads, templates, campaigns, pipeline data
31. tests -- smoke test suite covering all routes

## Failure Scenarios for Untested Capabilities

### 1. SQLite Job Queue at Swarm Scale
**Breakage scenario:** The email-queue agent and campaign-sender agent both write to `job_queue` table. If the spec doesn't prescribe exact column names and status values, they diverge: sender inserts `status='queued'`, worker queries `status='pending'`. Zero emails send. Silent failure.
**Mitigation:** Data Ownership table: only `campaign-sender` INSERTs to job_queue, only `email-queue` UPDATEs status. Exact status enum in spec: `pending`, `running`, `completed`, `failed`.

### 2. SSE at Swarm Scale
**Breakage scenario:** The sse-events agent builds the SSE endpoint reading from `campaign_progress` table. The email-queue agent is supposed to update that table after each send. But email-queue's brief doesn't mention campaign_progress -- it only knows about job_queue. Result: SSE endpoint works but always returns stale data.
**Mitigation:** Cross-Boundary Wiring Table: email-queue WRITES to campaign_progress after each job completion. sse-events READS campaign_progress. Both get this in their briefs.

### 3. SendGrid Webhook Integration
**Breakage scenario:** The delivery-webhooks agent expects POST body with `event: 'delivered'`. The sendgrid-client mock agent simulates webhooks but uses `event: 'deliver'` (different key name). Webhook handler silently drops all events.
**Mitigation:** Webhook payload schema defined ONCE in spec. Both agents reference the same schema.

### 4. File Uploads Cross-Boundary
**Breakage scenario:** The file-uploads agent creates `/api/files/upload` endpoint. The template-editor agent needs to attach files to templates but doesn't know the upload endpoint exists. The lead-import agent uploads CSVs but calls a different path `/api/import/upload`.
**Mitigation:** Single upload endpoint in Export Names Table. All agents importing files reference the same route name.

### 5. Multi-Tenant Data Isolation
**Breakage scenario:** 20+ agents write queries. Agent 17 (delivery-stats) aggregates across all campaigns without `WHERE workspace_id = ?`. A musician sees another musician's delivery stats.
**Mitigation:** Coordinated Behaviors Table includes workspace isolation as MANDATORY on every query. Prescriptive code block:
```python
# EVERY query on tenant-scoped tables MUST include:
campaigns = conn.execute(
    'SELECT ... FROM campaigns WHERE workspace_id = ? AND ...',
    (g.workspace['id'], ...)
).fetchall()
```

## Cross-Boundary Surfaces (Highest Risk)

### Surface 1: email-queue ↔ campaign-sender
- campaign-sender INSERTs rows to `job_queue` with campaign_id, lead_id, template content
- email-queue reads pending jobs, calls sendgrid-client, updates job status
- **Risk:** Column name divergence (FC1), transaction boundary confusion (FC29)
- **Prescription:** campaign-sender does NOT commit after INSERT -- the route handler commits after all jobs are enqueued

### Surface 2: delivery-webhooks ↔ sse-events
- delivery-webhooks receives POST from SendGrid (or mock), updates `email_events` table
- sse-events polls `email_events` + `campaign_progress` to stream updates
- **Risk:** delivery-webhooks commits but sse-events reads stale data due to SQLite read snapshot
- **Prescription:** sse-events opens a new connection per poll (no long-held read transaction)

### Surface 3: lead-import ↔ lead-tags ↔ pipeline-board
- lead-import creates leads + assigns default tags + sets initial pipeline stage
- lead-tags manages tag definitions referenced by lead-import
- pipeline-board displays leads by stage, expects specific stage values
- **Risk:** lead-import uses stage 'new' but pipeline-board expects 'New' (case mismatch)
- **Prescription:** PIPELINE_STAGES enum in spec, all agents reference it

## Open Questions (Resolved)

1. **Celery vs SQLite queue?** → SQLite queue. Proven pattern, no infrastructure.
2. **WebSocket vs SSE?** → SSE. One-way is sufficient, simpler.
3. **Customizable pipeline stages?** → Fixed enum for MVP. Customizable in Phase 2.
4. **Template engine for emails?** → Simple {{variable}} replacement. No Jinja2 in user content.
5. **File storage: local vs cloud?** → Local for MVP. Cloud in Phase 2.
6. **How many agents?** → 31. Vertical blueprint split, 4 shared + 27 feature.

## Feed-Forward

- **Hardest decision:** Replacing Celery/Redis with SQLite job queue. It simplifies infrastructure but the atomic claim pattern + separate worker process is a new pattern for swarm agents. If any agent misunderstands the claim pattern (e.g., does SELECT then UPDATE separately instead of atomic UPDATE...WHERE), the queue has race conditions.
- **Rejected alternatives:** Celery+Redis (too much infrastructure for MVP), WebSocket (overkill for one-way updates), Jinja2 templates for emails (security risk with user content), customizable pipeline stages (scope creep).
- **Least confident:** The 4-file email send chain (campaign-sender → job_queue table → email-queue worker → sendgrid-client → delivery-webhooks → sse-events) crosses 6 agent boundaries. This is the longest data flow ever attempted in a swarm build. If any link mismatches field names or transaction boundaries, emails silently fail. The spec must prescribe every column name, every function signature, and every commit/no-commit boundary in this chain.

## Refinement Findings

STATUS: PASS (5 gaps found, all addressable in plan)

### Gap 1: Worktree Commit Verification (FC37)
14/25 agents failed to commit in Run 049. At 31 agents, expect ~17 failures. The orchestrator MUST verify `git log --oneline -1 <branch>` per worktree before assembly and manually commit any unchanged branches.

### Gap 2: IDOR Ownership Checks (FC35) -- HIGHEST RISK
The brainstorm addresses workspace isolation via workspace_id but NOT per-resource ownership. 5/8 P1s in Run 049 were IDOR. The coordinated behaviors table must include: "Every detail/edit/delete route verifies `resource.created_by == g.user['id']` (or resource.workspace_id == g.workspace['id'] for workspace-scoped resources) after the 404 check."

### Gap 3: Transaction Boundary Annotations for Full Email Chain (FC29)
The brainstorm only prescribes "campaign-sender does NOT commit" but the full 6-agent chain needs commit/no-commit on every boundary:
- campaign-sender.enqueue_jobs() → does NOT commit (route handler commits after all jobs enqueued)
- email-queue.process_job() → COMMITS after each job (independent unit of work)
- sendgrid-client.send_email() → no DB writes (pure API call)
- delivery-webhooks.handle_event() → COMMITS after each webhook event
- email-queue → campaign_progress UPDATE → COMMITS (same transaction as job status update)

### Gap 4: Flow-Trace Review Agent Required
Flow-trace-reviewer caught the only P1 that 4 other reviewers missed in Client Music Planner (CSS class mismatch across 3 files). GigSheet has 3 critical 3+ file flows: SSE progress, SortableJS kanban, delivery dashboard charts. Flow-trace MUST be in the review phase.

### Gap 5: Reclaim Timestamp Must Use SQL datetime('now')
The timeout reclaim UPDATE must use `datetime('now')` as a SQL literal inside the statement, not a Python variable computed before the transaction:
```sql
UPDATE job_queue SET status='pending', claimed_at=NULL
WHERE status='running' AND claimed_at < datetime('now', '-5 minutes')
```
