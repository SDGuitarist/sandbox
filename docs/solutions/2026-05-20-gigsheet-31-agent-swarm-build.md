---
title: "GigSheet: 31-Agent Swarm Build -- Outreach Pipeline for Musicians"
date: 2026-05-20
run_id: "050"
category: swarm-build
tags: [flask, sqlite, swarm, 31-agents, email, sse, job-queue, multi-tenant, file-uploads, kanban]
agents: 31
loc: 7500
files: 96
smoke_tests: 46/46
merge_conflicts: 0
fc37_failures: 0
p1_findings: 8
p2_findings: 17
---

# GigSheet: 31-Agent Swarm Build

## What Was Built

An outreach and booking pipeline platform for gigging musicians. Musicians import
venue/promoter leads, build email templates with merge fields, send batch campaigns
via SendGrid (mock mode), track delivery (opens/clicks/bounces), and manage a kanban
pipeline from first contact through booking.

**Stack:** Flask + SQLite + Jinja2 + Bootstrap 5
**Scale:** 31 agents, 96 files, ~7,500 LOC, 46/46 smoke tests
**Records set:** Largest swarm build (up from 25 in VenueConnect), zero FC37 failures (down from 56% in VenueConnect), zero merge conflicts

## Key Technical Decisions

1. **SQLite job queue over Celery/Redis** -- Atomic claim via CTE+RETURNING, separate worker process. Eliminates Redis infrastructure dependency. Proven pattern from solution doc.
2. **SSE over WebSocket** -- Server-Sent Events for campaign progress. Single connection, heartbeat, 5-minute timeout. Simpler than Flask-SocketIO.
3. **Multi-tenant via workspace_id column** -- @require_workspace decorator sets g.workspace. Every query includes WHERE workspace_id = ?.
4. **File uploads to local storage** -- UUID filenames, ALLOWED_EXTENSIONS allowlist, PIL bomb protection, Content-Disposition: attachment.
5. **Merge field replacement** -- Simple {{variable}} str.replace() with markupsafe.escape(). No Jinja2 in user content (security).

## What Went Right

### Zero FC37 Failures
VenueConnect (25 agents) had 14/25 (56%) agents fail to commit. GigSheet (31 agents) had 0/31 (0%). The difference: explicit "FC37: YOU MUST git add and git commit" in every agent brief, plus the autopilot skill's "YOU MUST commit" emphasis.

### Zero Merge Conflicts
31 agents, 96 files, 0 conflicts. The vertical blueprint split with strict file ownership continues to produce clean assemblies.

### Spec Consistency Checker Caught 6 Contradictions
The pre-swarm gate found: shadow SQL writes not matching Data Ownership table, missing Export Names Table entries, function name mismatches (reclaim_timed_out vs reclaim_timed_out_jobs). All fixed before swarm launch.

### Deepening Research Agents Were High-ROI
4 targeted agents (SSE best practices, SQLite job queue, security sentinel, architecture strategist) found 6 P1s in the plan before a single line of code was written. The SSE agent corrected the per-poll connection pattern to single-connection. The architecture agent found 2 missing model functions.

## What Went Wrong

### 8 P1 Review Findings
Despite the most detailed spec to date, 5 review agents found 8 P1s:

| # | Finding | Failure Class | Agent |
|---|---------|---------------|-------|
| 1 | CSP blocks CDN scripts (Bootstrap + SortableJS dead) | NEW: CSP-CDN mismatch | flow-trace |
| 2 | Stored XSS via `\| safe` on html_body | FC26 variant (comment-not-code: "safe" label implies safety) | security |
| 3 | Missing lead_id workspace check in manage_recipients | FC35 (IDOR) | security |
| 4 | complete_job commits before message_id written | FC29 (transaction boundary) | flow-trace |
| 5 | Missing busy_timeout on Flask connections | NEW: pragma-per-connection | performance + learnings |
| 6 | Worker creates Flask app per job | NEW: app-per-job pattern | python + performance |
| 7 | Silent exception in context processor | FC10 variant (fail-open) | python |
| 8 | delivered_delta never passed to SSE | FC3 (dead wiring) | flow-trace |

### CSP-CDN Mismatch Is a New Pattern
The scaffold agent correctly added a CSP header with `script-src 'self'`. The pipeline-board agent correctly loaded SortableJS from CDN. The campaign-sender agent correctly loaded Bootstrap from CDN via base.html. No individual agent was wrong. The bug is invisible to any single-file reviewer -- it only appears when you trace from `__init__.py` (CSP header) across `base.html` (CDN script tag) to `pipeline_board/index.html` (SortableJS). This is a new cross-file failure pattern specific to CSP + CDN in swarm builds.

### FC35 Still the Top Finding
Despite prescriptive ownership checks in the Coordinated Behaviors table, manage_recipients still missed the lead_id validation. The pattern: agents check the primary resource (campaign) but not the referenced resources (lead_ids). The spec needs to prescribe validation of ALL resource IDs in request data, not just the URL parameter.

## Risk Resolution (Feed-Forward Chain Closure)

**Brainstorm risk:** "The 6-agent email send chain crosses 6 agent boundaries. If any link mismatches field names or transaction boundaries, emails silently fail."

**What actually happened:** The flow-trace reviewer found 2 bugs in the chain:
1. `complete_job` committed before `message_id` was written (transaction boundary -- exactly the predicted risk)
2. `delivered_delta` was never passed to `update_campaign_progress` (dead wiring)

Both were fixed in the review phase. The field names were consistent throughout (campaign_id, recipient_id, message_id all matched). The Transaction Boundary Annotations in the spec prevented the wider class of commit-ordering bugs -- only the worker's dual-commit pattern slipped through because the worker was partially rewritten during deepening.

**Lesson:** When deepening changes code patterns, the new patterns need the same transaction boundary analysis as the original spec. The deepening step introduced `complete_job` (which commits) without updating the worker's commit flow.

## New Failure Patterns

### CSP-CDN Script Source Mismatch
When a scaffold agent adds CSP headers and other agents add CDN scripts, the CSP will block the CDN unless the spec prescribes the exact CSP domains list. Add to spec template: if any agent uses CDN scripts, the CSP must include those domains.

### App-Per-Job in Worker Process
Swarm agents that build standalone worker processes tend to call `create_app()` inside the processing function (because they need app context for config/models). The spec must prescribe where `create_app()` is called -- once at module level, not per-job.

### PRAGMA Per-Connection
SQLite PRAGMAs like `busy_timeout` are per-connection, not per-database. Every code path that opens a SQLite connection (Flask get_db, worker, SSE generator) must set the same pragmas. The spec must list required pragmas as a Coordinated Behavior.

## Review Agent Performance

| Agent | P1 | P2 | P3 | Unique Finds | ROI |
|-------|----|----|-----|-------------|-----|
| flow-trace-reviewer | 2 | 1 | 0 | 3 (CSP, commit order, delivered_delta) | HIGHEST |
| security-sentinel | 2 | 5 | 4 | 2 (XSS, IDOR recipients) | HIGH |
| performance-oracle | 5 | 7 | 6 | 3 (pipeline unbounded, busy_timeout, N+1 bulk) | HIGH |
| kieran-python-reviewer | 5 | 10 | 7 | 2 (app-per-job, context processor) | HIGH |
| learnings-researcher | 0 | 1 | 0 | 0 (WAL verification, already noted) | MEDIUM |

**Flow-trace was the highest-ROI agent.** Its 3 P1 finds (CSP blocking, commit ordering, delivered_delta) were all cross-file bugs invisible to single-file reviewers. This validates the brainstorm refinement's Gap 4 recommendation to always include flow-trace.

## Deferred Items (P2s)

- 050-D1: Pipeline board loads ALL leads (no per-stage LIMIT) -- MEDIUM
- 050-D2: Campaign editor loads up to 10K leads for checkbox -- MEDIUM
- 050-D3: N+1 query in bulk pipeline move -- MEDIUM
- 050-D4: No pagination on campaign/template/file lists -- MEDIUM
- 050-D5: Analytics aggregation in Python instead of SQL SUM() -- LOW
- 050-D6: Webhook endpoint lacks SendGrid signature verification -- MEDIUM (mock mode OK)
- 050-D7: Missing type hints on 59 model functions -- LOW
- 050-D8: SSE generator missing WAL/busy_timeout pragmas -- LOW
- 050-D9: GET logout susceptible to CSRF -- LOW
- 050-D10: No HSTS header -- LOW

## Feed-Forward

- **Hardest decision:** Rewriting send_worker.py during deepening to use CTE+RETURNING and models functions. The rewrite introduced a new commit-ordering bug that the original simpler pattern didn't have.
- **Rejected alternatives:** Keeping the per-poll SQLite connection in SSE (research showed single connection is better), keeping BLOCKED_EXTENSIONS denylist (security switched to allowlist).
- **Least confident:** The CSP-CDN mismatch pattern is new and hard to prevent in swarm specs. The spec template needs a "CDN Dependencies" section that feeds into the CSP header prescription.
