---
title: "Multi-Tenant API Gateway"
date: 2026-04-05
status: draft
origin: "autopilot session — Flask + SQLite compound engineering run"
---

# Multi-Tenant API Gateway — Brainstorm

## Problem

Teams and products need to expose multiple backend services through a single entry point. Managing multiple service URLs, authenticating callers, and tracking usage is done ad-hoc today. We need a gateway that: (1) lets admins register backend services with a short alias, (2) lets API callers route requests through the alias, (3) authenticates each call with a per-tenant API key, and (4) logs latency + status per request for observability.

Who has it: platform engineering teams, SaaS providers with multiple microservices, API aggregation use cases.

## Context

- Flask + SQLite only (no Redis, no Celery, no external queue)
- Proxy means: receive request at `/proxy/<alias>/<path>`, validate API key, forward to `base_url + "/" + path`, return response
- Tenant = an org or user who has API keys and registered services
- Metrics per tenant = request count, latency, status codes
- Prior art available: api-key-manager.md (salted SHA-256 + prefix lookup), url-health-monitor.md (SSRF two-layer defense), flask-url-shortener-api.md (alias routing)

## Options

### Option A: Flat schema — one table per concern
One `tenants` table, one `services` table (tenant_id FK), one `api_keys` table (tenant_id FK), one `request_logs` table (tenant_id + service_id FK).

**Pros:**
- Simple schema, easy queries
- Tenant isolation via WHERE tenant_id = ?
- Straightforward metrics: GROUP BY tenant_id, service_id

**Cons:**
- request_logs will grow unboundedly — needs pruning or index care
- No per-service-per-key granularity (all keys can proxy all services for a tenant)

### Option B: Key-scoped service access
API keys have an explicit `allowed_services` list (JSON or join table). A key can only proxy services it's authorized for.

**Pros:**
- Finer-grained authorization
- Enables "read-only key for service A only" pattern

**Cons:**
- More complex validation path (extra join or JSON parse per request)
- Overkill for MVP — most users want "one key = access to all my services"

### Option C: Async metrics logging (write to queue, flush in background)
Log raw request events to a queue table; a background flush job aggregates into metrics.

**Pros:**
- Proxy latency not affected by log write
- Can aggregate more efficiently

**Cons:**
- Worker process required (more moving parts)
- Adds complexity for what is primarily a sync request path
- SQLite WAL handles concurrent writes fine at moderate load

## Tradeoffs

- **Authorization granularity vs. complexity**: Option A (tenant-level) is simpler and sufficient for MVP. Option B (key-scoped) is better for production but doubles implementation surface.
- **Sync vs. async logging**: Sync logging (Option A) blocks the proxy response by one SQLite write (~1ms on SSD). For MVP workloads this is acceptable. Async adds resilience but requires a background worker.
- **Metrics pre-aggregation vs. raw logs**: Raw logs (full row per request) are easy to implement and flexible for querying. Pre-aggregated counters are O(1) to query but lose per-request detail. Choose raw logs; add summary view if needed.

## Decision

**Option A: Flat schema, sync logging, tenant-level key authorization.**

Reasons:
1. Simpler to implement and verify correct
2. Sufficient for the stated requirements
3. SSRF and API key auth are higher-risk areas — focus complexity budget there
4. Can evolve to Option B later without breaking schema (just add a join table)

## Open Questions

1. **SSRF at proxy time**: Registered `base_url` could be `http://localhost:5432`. Block at registration (hostname check) AND refuse to follow redirects at proxy time. (Lesson from url-health-monitor solution doc.)
2. **Request body passthrough**: Does the gateway forward query params, headers, and body transparently? For MVP: forward query params and body, forward a safe subset of headers (drop Host, Authorization from upstream response).
3. **Response streaming**: For large responses, streaming avoids memory spike. `requests` + `stream=True` + Flask's `Response(stream_with_context(...))` is the pattern. Decision: implement streaming for MVP.
4. **Alias uniqueness**: Per-tenant or global? Global aliases risk collision. Per-tenant aliases mean `/proxy/<alias>` needs tenant resolution from the API key first. Decision: per-tenant aliases (key determines tenant, tenant determines service lookup).
5. **Metrics endpoint**: What does it return? Per-service aggregates (count, avg_latency_ms, error_rate) grouped by time window? Decision: return aggregate stats per service for the requesting tenant.

## What We're NOT Building

- Rate limiting (can be added later via request_logs counts)
- Circuit breaker / retry logic
- Response caching
- Request transformation / header rewriting beyond safe passthrough
- Admin UI
- Multi-region or high-availability SQLite

## Feed-Forward

- **Hardest decision:** Whether to use per-tenant alias namespacing (requires key→tenant lookup before service lookup, 2 DB reads per request) vs. global aliases (simpler but collision-prone). Chose per-tenant — correctness over simplicity.
- **Rejected alternatives:** Async metrics queue (adds worker process complexity with little benefit at SQLite scale); key-scoped service access (overkill for MVP, doubles auth validation complexity).
- **Least confident:** SSRF defense completeness at proxy time — registered-URL validation blocks obvious attacks, but HTTP redirect chains to private IPs require `allow_redirects=False` AND the initial request timeout must be short enough to prevent slow-loris on the gateway worker thread.
