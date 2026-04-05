# Next Five Apps — Maximizing Compound Learning

Sequenced to force new patterns while cross-referencing everything built so far. Each app introduces 2-3 new problem domains while reusing 3-4 existing ones.

## Prerequisites (8 apps already built)

1. CLI Todo (argparse, JSON storage)
2. URL Shortener (CSPRNG, redirects, click tracking)
3. Job Queue (atomic claims, retries, timeouts, WAL)
4. API Key Manager (salted hashing, rate limiting, BEGIN IMMEDIATE)
5. Distributed Task Scheduler (cron expressions, scheduler process)
6. URL Health Monitor (HTTP checks, time-series)
7. File Upload Service (binary handling, PIL decompression bombs, denylist)
8. Multi-Tenant API Gateway (SSRF defense, proxying, multi-tenancy)

---

## App 9: Event-Sourced Audit Log Service

```
/autopilot "Build an event-sourced audit log service — append-only event store, reconstruct entity state from events, query events by entity/type/time range with pagination. Include a projection endpoint that materializes current state. Use Flask and SQLite."
```

**New patterns:** Event sourcing, append-only storage, state reconstruction, cursor-based pagination
**Reuses:** SQLite indexing (job queue), timestamp handling (scheduler's ISO8601 lesson), input validation (API key manager), JSON payload storage (job queue)
**Why this order:** Pagination and event sourcing are foundational patterns missing from the knowledge base. Every subsequent app benefits from knowing how to page through results and model state changes.

---

## App 10: Real-Time Chat Rooms with Message History

```
/autopilot "Build a chat room API — create rooms, join/leave rooms, post messages, poll for new messages since a cursor, and list message history with pagination. Include rate limiting per user using the fixed-window pattern. Use Flask and SQLite."
```

**New patterns:** Long-polling, cursor-based sync, multi-entity relationships (users → rooms → messages), foreign keys
**Reuses:** Rate limiting (API key manager's BEGIN IMMEDIATE), pagination (audit log), CSPRNG for tokens (URL shortener), atomic operations (job queue claim pattern)
**Why this order:** Forces relational modeling (join tables, foreign keys) — every app so far used a single table. The cursor-based polling pattern is distinct from job queue polling and teaches a different concurrency model.

---

## App 11: Feature Flag Service with Rollout Rules

```
/autopilot "Build a feature flag management service — create flags with rollout rules (percentage, user allowlist, environment targeting), evaluate flags for a given user/context, track evaluation counts, and support flag dependencies (flag B requires flag A enabled). Use Flask and SQLite."
```

**New patterns:** Rule evaluation engine, dependency graphs (DAG), percentage-based rollout (deterministic hashing), configuration-as-data
**Reuses:** API key validation middleware (API key manager), JSON rule storage (job queue payloads), atomic counters (URL shortener clicks), multi-table schema (chat rooms)
**Why this order:** Introduces graph dependencies and rule engines — a fundamentally different problem shape from CRUD/queue patterns. The deterministic hashing for percentage rollout will conflict with the CSPRNG lesson, forcing a nuanced "when to use which" solution doc.

---

## App 12: Schema Migration Runner

```
/autopilot "Build a database migration runner — register migration files (up/down SQL), track applied migrations in a migrations table, support migrate-up, migrate-down, and status commands. Include dry-run mode and lock-based protection against concurrent migrations. Use Flask API + CLI mode and SQLite."
```

**New patterns:** Schema versioning, up/down migrations, advisory locks, dry-run mode, dual interface (API + CLI), transaction safety for DDL
**Reuses:** BEGIN IMMEDIATE (API key manager), WAL verification (job queue), atomic state transitions (job queue claim), file handling (upload service), CLI patterns (todo app's argparse)
**Why this order:** Every app so far uses `CREATE TABLE IF NOT EXISTS` — this forces confronting what happens when schemas evolve. The lock-based concurrency protection is a different pattern from row-level atomicity. Dual CLI+API interface is new.

---

## App 13: Service Mesh Dashboard (Capstone)

```
/autopilot "Build a service mesh dashboard that integrates the URL shortener, job queue, API key manager, and health monitor into a unified dashboard. Register services with health check URLs, authenticate with API keys, display aggregate health status, queue periodic health checks as jobs, and show a timeline of events from the audit log. Use Flask and SQLite."
```

**New patterns:** Service integration/orchestration, HTTP client calls between services, aggregate views across data sources, dashboard composition, circuit breaker for downstream failures
**Reuses:** Everything — health monitor (URL checks), job queue (periodic tasks), API keys (auth), audit log (event timeline), URL shortener (service aliases), SSRF protection (API gateway), pagination (audit log), rate limiting (chat rooms)
**Why this order:** This is the capstone. It forces the system to compose patterns from all previous apps into one coherent service. The review agents will have 12 solution docs to cross-reference — maximum compounding. Any pattern that was learned wrong will surface here when it's used in a different context.

---

## Expected Compounding Trajectory

| App | Solution Docs Available | Cross-References Expected |
|-----|------------------------|--------------------------|
| 9 - Audit Log | 8 | 3-4 (timestamps, validation, indexing) |
| 10 - Chat Rooms | 9 | 5-6 (pagination, rate limiting, atomic ops) |
| 11 - Feature Flags | 10 | 4-5 (API keys, counters, rule storage) |
| 12 - Migration Runner | 11 | 6-7 (locks, WAL, transactions, CLI+API) |
| 13 - Service Mesh | 12 | 10+ (everything converges) |

The final app should produce the densest solution doc in the system — and if the compounding thesis holds, it should also have the fewest P1 findings because the system has already learned most of the patterns it needs.
