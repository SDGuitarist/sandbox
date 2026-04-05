---
title: "Webhook Delivery System"
date: 2026-04-05
status: complete
origin: "conversation"
---

# Webhook Delivery System — Brainstorm

## Problem
Developers need a way to register webhook endpoints (URL + secret + event types), trigger deliveries when events occur, and reliably deliver HTTP POST requests to subscriber URLs with retries and exponential backoff. Failed deliveries must be tracked with attempt history.

## Context
- Stack: Python + Flask + SQLite (explicitly required)
- The /workspace/job-queue/ project is a working Flask job queue API — the question is whether to reuse it or embed queue logic directly
- Exponential backoff = delay doubles each retry (e.g., 10s, 20s, 40s, 80s...)
- Need: webhook registration, event dispatch, delivery tracking, retry scheduling
- Prior art: job-queue solution doc has the atomic claim + WAL pattern; url-shortener has Flask+SQLite safety patterns

## Options

### Option A: Embed queue logic directly (no dependency on job-queue service)
Build the webhook system as a self-contained Flask app with its own SQLite tables: `webhooks` (registrations) + `deliveries` (attempts). Workers poll a `deliveries` table directly using the same atomic claim pattern from the job-queue solution doc.
- Pros: No inter-service HTTP overhead; single deployable; simpler ops; easier to add exponential backoff (computed delay is a column on the delivery row)
- Cons: Duplicates queue logic; two places to maintain retry/claim code

### Option B: Call the job-queue API over HTTP
Submit each webhook delivery as a job to POST /jobs on the existing job-queue service. Workers poll POST /jobs/claim from the job-queue API.
- Pros: Reuses proven job queue; no queue code to maintain
- Cons: Adds HTTP coupling (job-queue must be running); job-queue has no built-in scheduled delay for exponential backoff; payload is opaque JSON (webhook metadata must be embedded); harder to query delivery history per webhook

### Option C: Shared SQLite file (embed job-queue tables, different Flask app)
Both apps share the same SQLite file. Webhook app inserts into the jobs table; job-queue workers claim them.
- Pros: Reuses claim logic without HTTP overhead
- Cons: Tight coupling through shared DB file; schema coupling; deployment complexity; defeats the purpose of a separate service

## Tradeoffs
- **Simplicity vs. reuse:** Option A duplicates ~30 lines of claim logic but is far simpler to understand, deploy, and test independently. Option B reuses proven code but adds an HTTP dependency that makes the webhook system non-self-contained.
- **Exponential backoff scheduling:** Option A can add a `deliver_after TIMESTAMP` column on the delivery row — the claim query filters `WHERE deliver_after <= now`. Option B can't schedule jobs for future execution (the job-queue has no delay/schedule feature).
- **Delivery history:** Option A has full query access to all delivery attempts. Option B embeds history in job payloads (opaque).

## Decision
**Option A** — self-contained Flask app with embedded queue logic. The exponential backoff requirement specifically requires scheduling deliveries for future times (`deliver_after`), which the existing job-queue cannot do. Building directly also keeps the project deployable independently.

Schema:
```
webhooks(id, url, secret, events JSON, is_active, created_at)
deliveries(id, webhook_id, event_type, payload JSON, status, attempt_count, max_attempts, next_attempt_at, last_error, created_at, completed_at)
```

Status machine for deliveries: `pending → delivering → delivered | failed`

Endpoints:
- `POST /webhooks` — register a webhook (url, secret, events list, max_attempts)
- `GET /webhooks/<id>` — get registration details
- `DELETE /webhooks/<id>` — deactivate webhook
- `POST /events` — dispatch an event (event_type, payload) — fans out to all matching active webhooks, creates one delivery row per webhook
- `POST /deliveries/claim` — worker atomically claims next due delivery
- `POST /deliveries/<id>/complete` — worker reports success (HTTP 2xx received)
- `POST /deliveries/<id>/fail` — worker reports failure; schedules retry with exponential backoff if attempts remain
- `GET /webhooks/<id>/deliveries` — delivery history for a webhook

Exponential backoff formula: `delay_seconds = base_delay * (2 ** attempt_count)` where `base_delay = 10`. So: 10s, 20s, 40s, 80s, 160s...

Worker flow: claim delivery → POST to webhook URL with HMAC-SHA256 signature header → if 2xx complete, else fail (triggers retry scheduling).

## Open Questions
- Should HMAC signing use the webhook secret? Yes — `X-Webhook-Signature: sha256=<hmac>`
- Should the `POST /events` endpoint be synchronous (insert deliveries) or async? Synchronous — insert delivery rows and return, workers handle the actual HTTP calls.
- What counts as success? Any HTTP 2xx response from the target URL. Non-2xx and connection errors both count as failures.

## Feed-Forward
- **Hardest decision:** Option A (embed queue) vs. Option B (call job-queue API). Chose A because exponential backoff requires future scheduling (`deliver_after` timestamp), which the existing job-queue cannot provide without modification.
- **Rejected alternatives:** Option B (HTTP coupling + no scheduled delay), Option C (shared SQLite file = tight coupling without the benefits of a shared service).
- **Least confident:** Whether SQLite is adequate for the fan-out case — `POST /events` must insert one delivery row per matching webhook in a single transaction. With many webhooks registered for the same event, this could be a slow transaction. At small scale this is fine; at large scale, a message broker would be better. For this scope: proceed with SQLite and note the limitation.
