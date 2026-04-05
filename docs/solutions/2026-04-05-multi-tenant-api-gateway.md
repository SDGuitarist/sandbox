---
title: Multi-Tenant API Gateway
date: 2026-04-05
tags: [flask, sqlite, proxy, api-keys, ssrf, multi-tenant]
module: api_gateway
lesson: SSRF requires two layers (registration-time IP block + allow_redirects=False at proxy time); sqlite3 context manager does NOT close connections; key prefix collision loop must use continue not return None
origin_plan: docs/plans/2026-04-05-feat-multi-tenant-api-gateway-plan.md
origin_brainstorm: docs/brainstorms/2026-04-05-multi-tenant-api-gateway.md
---

# Multi-Tenant API Gateway

## Problem

Multiple backend services need to be routed through a single entry point. Callers need API key authentication, service aliases for short URLs, and per-tenant request metrics for observability.

## Solution

Flask API with three layers:
1. **Admin plane** (`routes_admin.py`) — tenant/service/key management, protected by `X-Admin-Token` header
2. **Proxy plane** (`routes_proxy.py`) — `ANY /proxy/<alias>/<path>`, Bearer token auth, streaming upstream forward
3. **Metrics** — `GET /tenants/<id>/metrics` returns per-service count/success/error/avg/p95 latency

Key architecture:
- Per-tenant alias namespace: key → tenant → service lookup (2 DB reads per proxy request; correct over fast)
- API keys: `secrets.token_urlsafe(32)` plaintext, first 16 chars stored as `key_prefix` for indexed lookup, `SHA-256(salt + plaintext)` as `key_hash`, `hmac.compare_digest` for timing-safe comparison
- SQLite WAL + busy_timeout on every connection; `db.get_connection()` is a `@contextmanager` that always calls `conn.close()`
- Streaming response: `requests(stream=True)` + Flask `stream_with_context` + `upstream.close()` in generator `finally`
- `allow_redirects=False` in every proxy request — non-negotiable SSRF defense

## Why This Approach

- **No Redis/Celery** — SQLite WAL handles concurrent writes at moderate load
- **Per-tenant aliases** — prevents collision across tenants; key determines tenant, tenant determines alias
- **Sync logging** — one SQLite write (~1ms) after headers received; async queue would add worker complexity
- **Flat schema** — tenants + services + api_keys + request_logs; easy GROUP BY for metrics

## Risk Resolution

> **Flagged risk:** "SSRF defense completeness at proxy time — registered-URL validation blocks obvious attacks, but HTTP redirect chains to private IPs require allow_redirects=False AND the initial request timeout must be short enough to prevent slow-loris on the gateway worker thread."

> **What actually happened:** Review confirmed `allow_redirects=False` and `timeout=10` were correctly implemented. Additionally, the SSRF guard was upgraded from checking individual predicates (is_loopback, is_private, etc.) to using `ip.is_global` which is more comprehensive for IPv6. CGNAT (100.64.0.0/10) was added as an explicit block since `is_global` doesn't cover it. DNS rebinding remains a known accepted risk at the MVP level.

> **Lesson learned:** Use `ip.is_global` for SSRF IP checks (covers IPv6 site-local, link-local, and more) — don't enumerate individual `is_loopback or is_private or is_link_local...` predicates. Supplement with explicit CGNAT block. `allow_redirects=False` is mandatory and must never be removed.

## Key Decisions

| Decision | Chosen | Rejected | Reason |
|----------|--------|----------|--------|
| Alias namespace | Per-tenant (key→tenant→alias) | Global aliases | Collision-proof; 2 DB reads is acceptable |
| Metrics | Raw logs + GROUP BY | Pre-aggregated counters | Flexible queries; P95 computed in Python |
| Auth | GATEWAY_ADMIN_TOKEN env var | No auth, OAuth | Simple; avoids bootstrapping problem |
| Logging | Sync (after first byte received) | Async queue | No worker needed; latency is TTFB, not full transfer |

## Gotchas

### sqlite3.Connection context manager does NOT close the connection
```python
# WRONG — this commits/rollbacks on exit but leaves the connection OPEN
with sqlite3.connect(db_path) as conn:
    ...

# RIGHT — use a contextmanager wrapper that always calls close()
@contextlib.contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()
```
This affects every Flask project using SQLite. The fd leak only shows up under load.

### Streaming upstream response — always close the upstream in generator finally
```python
def generate():
    try:
        for chunk in upstream.iter_content(chunk_size=8192):
            if chunk:
                yield chunk
    finally:
        upstream.close()  # mandatory — prevents socket leak on client disconnect
```
Without the `finally`, upstream sockets leak when clients disconnect mid-stream.

### Key prefix collision: use `continue`, not `return None`
```python
for row in rows:
    if hmac.compare_digest(candidate_hash, row["key_hash"]):
        if row["expires_at"] and row["expires_at"] < now_str:
            continue  # NOT return None — another row with same prefix may be valid
        return dict(row)
```
`return None` on first expired row blocks all valid keys that share the same 16-char prefix.

### SSRF: use `ip.is_global` not individual predicates
```python
# WRONG — misses CGNAT, some IPv6 ranges
if ip.is_loopback or ip.is_private or ip.is_link_local:
    return False

# RIGHT
if not ip.is_global:
    return False
# Also add explicit CGNAT block
if ip.version == 4 and ip in ipaddress.ip_network("100.64.0.0/10"):
    return False
```

### Header injection — strip CRLF before forwarding
```python
for k, v in headers.items():
    if '\r' in v or '\n' in v or '\0' in v:
        continue  # reject CRLF injection attempts
```
Also strip `X-Forwarded-For`, `X-Forwarded-Host`, `X-Real-IP` — these are gateway-controlled, not caller-controlled.

### Query string forwarding — use urlencode, not raw bytes
```python
# WRONG — raw bytes decode may fail; double-? if base_url has query string
query_string = request.query_string.decode("utf-8")
target_url = f"{target_url}?{query_string}"

# RIGHT
query_string = urlencode(request.args, doseq=True)
separator = "&" if "?" in target_path else "?"
target_url = f"{target_path}{separator}{query_string}" if query_string else target_path
```

### expires_at must be validated before storage
```python
# Validate format and that it's in the future
if not _ISO8601_RE.match(value):
    abort(400, "expires_at must be ISO8601")
if normalized <= now_str:
    abort(400, "expires_at must be in the future")
```
Without validation, `"aaaa"` compares as expired (< any ISO datetime), `"zzzz"` compares as never-expiring.

### Admin routes require authentication
Every admin endpoint (create tenant, list services, generate keys, view metrics) must require authentication. Add `GATEWAY_ADMIN_TOKEN` env var, validate with `hmac.compare_digest` to prevent timing attacks. Refuse to start if env var is not set.

### P95 latency — nearest-rank formula
```python
import math
idx = max(0, math.ceil(len(lats) * 0.95) - 1)  # nearest-rank, 0-indexed
p95 = lats[idx]
```
`int(len(lats) * 0.95) - 1` gives the 94th percentile and can return -1 for 1-element lists.

## Feed-Forward

- **Hardest decision:** Per-tenant alias namespace (2 DB reads per proxy request) vs. global aliases (1 read, collision risk). Chose per-tenant — correctness over micro-optimization.
- **Rejected alternatives:** Async metrics queue (adds worker process), key-scoped service access (doubles auth path complexity), global aliases (collision-prone).
- **Least confident:** DNS rebinding remains a known gap — registration-time IP check can be bypassed if DNS TTL expires and IP changes to a private address. Production deployments should add a proxy-time IP re-check on the resolved upstream URL before each request.
