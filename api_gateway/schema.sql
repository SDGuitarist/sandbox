-- Multi-Tenant API Gateway Schema

-- tenants: top-level org/user isolation unit
CREATE TABLE IF NOT EXISTS tenants (
    id         TEXT PRIMARY KEY,          -- UUID v4
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- services: backend services registered per tenant
CREATE TABLE IF NOT EXISTS services (
    id         TEXT PRIMARY KEY,          -- UUID v4
    tenant_id  TEXT NOT NULL REFERENCES tenants(id),
    alias      TEXT NOT NULL,             -- short name used in proxy path
    base_url   TEXT NOT NULL,             -- upstream base URL (SSRF-checked at registration)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tenant_id, alias)              -- alias is per-tenant namespace
);

-- api_keys: authentication credentials per tenant
CREATE TABLE IF NOT EXISTS api_keys (
    id         TEXT PRIMARY KEY,          -- UUID v4
    tenant_id  TEXT NOT NULL REFERENCES tenants(id),
    name       TEXT NOT NULL DEFAULT '',
    key_prefix TEXT NOT NULL,             -- first 16 chars of plaintext for fast lookup
    key_salt   TEXT NOT NULL,             -- random hex salt
    key_hash   TEXT NOT NULL,             -- SHA-256(salt + plaintext)
    status     TEXT NOT NULL DEFAULT 'active'
                   CHECK(status IN ('active', 'revoked')),
    expires_at TEXT,                      -- NULL = never expires
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Index for fast prefix-based key lookup
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix
    ON api_keys(key_prefix);

CREATE INDEX IF NOT EXISTS idx_api_keys_tenant
    ON api_keys(tenant_id);

-- request_logs: one row per proxied request
CREATE TABLE IF NOT EXISTS request_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id    TEXT NOT NULL REFERENCES tenants(id),
    service_id   TEXT NOT NULL REFERENCES services(id),
    api_key_id   TEXT NOT NULL REFERENCES api_keys(id),
    method       TEXT NOT NULL,
    path         TEXT NOT NULL,
    status_code  INTEGER,
    latency_ms   INTEGER,
    error_message TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for metrics queries
CREATE INDEX IF NOT EXISTS idx_request_logs_tenant_created
    ON request_logs(tenant_id, created_at);

CREATE INDEX IF NOT EXISTS idx_request_logs_service_created
    ON request_logs(service_id, created_at);
