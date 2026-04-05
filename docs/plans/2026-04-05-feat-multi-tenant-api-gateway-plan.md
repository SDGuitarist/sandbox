---
title: "Multi-Tenant API Gateway"
type: feat
status: active
date: 2026-04-05
origin: docs/brainstorms/2026-04-05-multi-tenant-api-gateway.md
feed_forward:
  risk: "SSRF defense completeness at proxy time — registered-URL validation blocks obvious attacks, but HTTP redirect chains to private IPs require allow_redirects=False AND the initial request timeout must be short enough to prevent slow-loris on the gateway worker thread."
  verify_first: true
---

# feat: Multi-Tenant API Gateway

## Enhancement Summary

**Deepened on:** 2026-04-05
**Research agents used:** solution-doc-searcher (6 relevant docs found)

### Key Corrections From Research

- **API key auth**: Use salted SHA-256 + 16-char prefix for lookup, HMAC.compare_digest for comparison. Never store plaintext. (Source: 2026-04-05-api-key-manager.md)
- **SSRF two-layer defense**: Block private/loopback IPs at registration via `socket.getaddrinfo()` + `ipaddress` check AND set `allow_redirects=False` in the proxy request. (Source: 2026-04-05-url-health-monitor.md)
- **WAL mandatory**: `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=5000` on every connection. (Source: 2026-04-05-flask-url-shortener-api.md)
- **Timestamps inside BEGIN IMMEDIATE**: Capture `now` inside the transaction, not before. (Source: 2026-04-05-distributed-task-scheduler.md)

## What Must Not Change

- UUID tenant IDs and API key IDs — UUID4 only, validated before any path construction
- API key plaintext is never stored — only `key_hash` (salted SHA-256) and `key_prefix` (first 16 chars for lookup)
- Proxy path: `/proxy/<alias>/<path:remainder>` — `alias` resolved per-tenant (key→tenant→service)
- All DB connections use WAL + busy_timeout
- `allow_redirects=False` in proxy requests — non-negotiable SSRF defense

## Prior Phase Risk

> "SSRF defense completeness at proxy time — registered-URL validation blocks obvious attacks, but HTTP redirect chains to private IPs require allow_redirects=False AND the initial request timeout must be short enough to prevent slow-loris on the gateway worker thread."

**Plan response**: First task in Phase 2 is implementing `_is_safe_url()` (registration-time SSRF check). Proxy uses `requests.request(..., allow_redirects=False, timeout=10)`. Timeout of 10s caps slow-loris risk. Both layers are non-negotiable; plan fails if either is absent.

## Smallest Safe Plan

### Phase 1: Schema + DB layer
Files: `api_gateway/schema.sql`, `api_gateway/db.py`

Schema tables:
- `tenants (id TEXT PK, name TEXT UNIQUE NOT NULL, created_at TEXT)`
- `services (id TEXT PK, tenant_id TEXT FK→tenants, alias TEXT NOT NULL, base_url TEXT NOT NULL, created_at TEXT, UNIQUE(tenant_id, alias))`
- `api_keys (id TEXT PK, tenant_id TEXT FK→tenants, name TEXT, key_prefix TEXT NOT NULL, key_hash TEXT NOT NULL, key_salt TEXT NOT NULL, status TEXT CHECK(status IN ('active','revoked')) DEFAULT 'active', expires_at TEXT, created_at TEXT)`
- `request_logs (id INTEGER PK AUTOINCREMENT, tenant_id TEXT FK→tenants, service_id TEXT FK→services, api_key_id TEXT FK→api_keys, method TEXT, path TEXT, status_code INTEGER, latency_ms INTEGER, error_message TEXT, created_at TEXT)`

Indexes:
- `api_keys(key_prefix)` — fast prefix lookup
- `request_logs(tenant_id, created_at)` — metrics queries
- `request_logs(service_id, created_at)` — per-service metrics

`db.py`: `get_connection()` with WAL+timeout+foreign_keys, `init_db()`, `generate_id()` (UUID4), UUID validation regex.

Gate: `python db.py` creates tables cleanly.

### Phase 2: Tenant + Service management routes
Files: `api_gateway/routes_admin.py`

Endpoints:
- `POST /tenants` — create tenant (`name` required, unique)
- `GET /tenants` — list tenants
- `POST /tenants/<tenant_id>/services` — register service (`alias`, `base_url`; SSRF check on base_url)
- `GET /tenants/<tenant_id>/services` — list services for tenant
- `DELETE /tenants/<tenant_id>/services/<service_id>` — remove service
- `POST /tenants/<tenant_id>/keys` — generate API key (returns plaintext once, stores hash)
- `GET /tenants/<tenant_id>/keys` — list keys (no plaintext)
- `DELETE /tenants/<tenant_id>/keys/<key_id>` — revoke key (set status='revoked')

SSRF helper `_is_safe_url(base_url)`:
1. Parse URL, verify scheme is http or https
2. Resolve hostname via `socket.getaddrinfo()`
3. Check each IP: reject if loopback, private, link-local, multicast, reserved
4. Return False if hostname fails to resolve

API key generation:
```python
import secrets, hashlib, hmac
plaintext = secrets.token_urlsafe(32)
key_prefix = plaintext[:16]
salt = secrets.token_hex(16)
key_hash = hashlib.sha256((salt + plaintext).encode()).hexdigest()
# Store: key_prefix, key_salt, key_hash
# Return: plaintext (once only)
```

API key lookup:
```python
prefix = submitted_key[:16]
rows = conn.execute("SELECT * FROM api_keys WHERE key_prefix=? AND status='active'", (prefix,))
for row in rows:
    candidate = hashlib.sha256((row['key_salt'] + submitted_key).encode()).hexdigest()
    if hmac.compare_digest(candidate, row['key_hash']):
        # Check expires_at
        return row
```

Gate: all admin endpoints tested with curl.

### Phase 3: Proxy route
Files: `api_gateway/routes_proxy.py`

Endpoint: `ANY /proxy/<alias>/<path:remainder>`

Flow:
1. Extract API key from `Authorization: Bearer <key>` header
2. Look up key: `key_prefix` → `api_keys` → verify hash → check status='active' + expiry
3. Resolve `tenant_id` from key row
4. Look up service: `SELECT * FROM services WHERE tenant_id=? AND alias=?`
5. If not found: 404
6. Build target URL: `base_url.rstrip('/') + '/' + remainder + query_string`
7. Forward request: `requests.request(method, target_url, headers=safe_headers, data=body, stream=True, allow_redirects=False, timeout=10)`
8. Return streaming response to caller
9. Log to `request_logs`: tenant_id, service_id, api_key_id, method, path, status_code, latency_ms

Safe headers to forward: forward request headers except `Host`, `Authorization`, `Content-Length` (requests sets it). Forward response headers except `Transfer-Encoding`.

Streaming pattern:
```python
import requests
from flask import Response, stream_with_context

upstream = requests.request(..., stream=True, allow_redirects=False, timeout=10)
def generate():
    for chunk in upstream.iter_content(chunk_size=8192):
        yield chunk
return Response(stream_with_context(generate()), status=upstream.status_code, headers=dict(upstream.headers))
```

Gate: proxy a real public endpoint through an alias; confirm log row written.

### Phase 4: Metrics endpoint
Files: `api_gateway/routes_admin.py` (additional endpoint)

Endpoint: `GET /tenants/<tenant_id>/metrics`

Query params: `service_id` (optional), `since` (ISO8601, default 24h ago)

Returns per-service aggregate:
```json
{
  "tenant_id": "...",
  "since": "...",
  "services": [
    {
      "service_id": "...",
      "alias": "...",
      "total_requests": 42,
      "success_count": 40,
      "error_count": 2,
      "avg_latency_ms": 123.4,
      "p95_latency_ms": 280
    }
  ]
}
```

SQL: GROUP BY service_id with COUNT, AVG, and approximate P95 via subquery or Python computation from fetched rows.

Gate: upload a file, call proxy multiple times, verify metrics reflect calls.

### Phase 5: App wiring
Files: `api_gateway/app.py`, `api_gateway/db.py` (init_db call)

- Flask app factory
- Register both blueprints
- MAX_CONTENT_LENGTH = 10MB
- Error handlers: 400, 404, 413, 500
- `if __name__ == "__main__": init_db(); app.run(port=5008)`

## Rejected Options

- Async metrics queue: adds worker process; sync logging is ~1ms and acceptable at SQLite scale
- Key-scoped service access (per-key allowed_services): overkill for MVP; doubles auth path complexity
- Global aliases (vs. per-tenant): collision-prone; per-tenant requires 2 DB lookups but is correct
- Pre-aggregated metrics counters: loses per-request detail; raw logs + GROUP BY is flexible enough

## Risks And Unknowns

1. **SSRF at proxy time**: primary risk. Mitigated by two layers (registration check + allow_redirects=False + timeout).
2. **request_logs growth**: unbounded writes. For MVP, no pruning needed; add an index on created_at for range queries.
3. **Streaming response + SQLite write ordering**: log write happens after streaming starts. Latency is measured as `time.time()` before/after `requests.request()` call (not after full stream drain). This gives response-start latency, not full transfer latency — acceptable.
4. **Large request bodies**: `data=request.get_data()` reads entire body into memory before forwarding. For MVP this is acceptable (MAX_CONTENT_LENGTH=10MB cap).
5. **Concurrent writes under load**: WAL handles this; SQLite is single-writer so throughput is limited. Noted but out of scope.

## Most Likely Way This Plan Is Wrong

The SSRF check at registration may pass for a hostname that later resolves to a private IP (DNS rebinding). The proxy's `allow_redirects=False` does not defend against rebinding — only a re-check at proxy time would. For MVP we accept this risk and note it in the solution doc. Production deployments should add a proxy-time IP re-check.

## Scope Creep Check

Compare against brainstorm `docs/brainstorms/2026-04-05-multi-tenant-api-gateway.md`:
- Service registration with base URLs: ✓ in plan
- Proxy through short aliases: ✓ in plan
- API key authentication: ✓ in plan
- Per-tenant request/response metrics: ✓ in plan (Phase 4)
- Streaming responses: ✓ added during brainstorm open questions — in scope
- Rate limiting: ✗ explicitly NOT in brainstorm scope
- Circuit breaker: ✗ explicitly NOT in brainstorm scope

No scope creep.

## Acceptance Criteria

- [ ] `POST /tenants` creates a tenant and returns tenant_id
- [ ] `POST /tenants/<id>/services` with a private IP base_url returns 422
- [ ] `POST /tenants/<id>/services` with a valid public URL succeeds
- [ ] `POST /tenants/<id>/keys` returns a plaintext key (once); subsequent GET /keys does NOT show plaintext
- [ ] `GET /proxy/<alias>/anything` without Authorization header returns 401
- [ ] `GET /proxy/<alias>/anything` with a revoked key returns 401
- [ ] `GET /proxy/<alias>/path?q=1` with valid key proxies to `base_url/path?q=1` and returns upstream response
- [ ] `GET /proxy/<alias>/path` with valid key but non-existent alias returns 404
- [ ] After a proxied request, `GET /tenants/<id>/metrics` shows 1 request for that service
- [ ] `avg_latency_ms` in metrics is a positive integer

## Tests Or Checks

```bash
cd api_gateway
python db.py  # init DB

# Admin flows
curl -s -X POST http://localhost:5008/tenants -H 'Content-Type: application/json' -d '{"name":"acme"}' | jq
curl -s -X POST http://localhost:5008/tenants/<tid>/services -H 'Content-Type: application/json' \
  -d '{"alias":"httpbin","base_url":"https://httpbin.org"}' | jq

# Key generation
curl -s -X POST http://localhost:5008/tenants/<tid>/keys -H 'Content-Type: application/json' \
  -d '{"name":"test-key"}' | jq  # save .key

# SSRF rejection
curl -s -X POST http://localhost:5008/tenants/<tid>/services \
  -d '{"alias":"bad","base_url":"http://127.0.0.1:5432"}' | jq  # expect 422

# Proxy
curl -s http://localhost:5008/proxy/httpbin/get?foo=bar \
  -H 'Authorization: Bearer <key>' | jq

# Metrics
curl -s http://localhost:5008/tenants/<tid>/metrics | jq
```

## Rollback Plan

`api_gateway/` is a new directory — delete it. No existing files are modified. `uploads.db` is untouched.

## Claude Code Handoff Prompt

```text
Read docs/plans/2026-04-05-feat-multi-tenant-api-gateway-plan.md.

Repos and files in scope:
- api_gateway/schema.sql (new)
- api_gateway/db.py (new)
- api_gateway/routes_admin.py (new)
- api_gateway/routes_proxy.py (new)
- api_gateway/app.py (new)

Scope boundaries:
- Do NOT modify any existing project directories
- Do NOT add rate limiting, circuit breaker, or response caching
- Do NOT store API key plaintext in the DB
- All DB connections must use WAL + busy_timeout=5000
- allow_redirects=False is mandatory in the proxy request — non-negotiable

Key corrections from plan review:
- API key: salted SHA-256 + 16-char prefix lookup + hmac.compare_digest
- SSRF: socket.getaddrinfo + ipaddress check at registration + allow_redirects=False at proxy time
- Streaming: requests stream=True + Flask stream_with_context
- Latency: measured as time before/after requests.request() call, not after stream drain

Acceptance criteria:
- POST /tenants creates tenant
- POST /tenants/<id>/services with private IP returns 422
- POST /tenants/<id>/keys returns plaintext once
- Proxy with valid key forwards request and returns upstream response
- Proxy with missing/invalid/revoked key returns 401
- GET /tenants/<id>/metrics shows request count and avg latency

Required checks:
- python -c "import ast; ast.parse(open('routes_proxy.py').read())" (syntax)
- Manual curl test: proxy httpbin.org/get through alias
- Manual curl test: SSRF rejection with 127.0.0.1 base_url

Stop conditions:
- If SSRF check cannot be implemented safely, halt and report
- If streaming response causes response corruption, halt and report
```

## Sources

- Brainstorm: docs/brainstorms/2026-04-05-multi-tenant-api-gateway.md

## Feed-Forward

- **Hardest decision:** Per-tenant alias namespacing (key→tenant→service, 2 DB reads per proxy request) vs. global aliases (1 read, collision risk). Chose per-tenant — security correctness over minimal latency.
- **Rejected alternatives:** Async metrics logging (adds worker), key-scoped services (doubles auth complexity), global aliases (collision-prone).
- **Least confident:** DNS rebinding attack on registered base_urls — registration-time IP check can be bypassed if DNS TTL expires and IP changes. Production would need a proxy-time re-check; MVP accepts this risk.
