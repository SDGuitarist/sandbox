"""
Admin routes for the API gateway.

Endpoints:
  POST   /tenants                                   — create tenant
  GET    /tenants                                   — list tenants
  POST   /tenants/<tenant_id>/services              — register service (SSRF-checked)
  GET    /tenants/<tenant_id>/services              — list services
  DELETE /tenants/<tenant_id>/services/<service_id> — remove service
  POST   /tenants/<tenant_id>/keys                  — generate API key
  GET    /tenants/<tenant_id>/keys                  — list keys (no plaintext)
  DELETE /tenants/<tenant_id>/keys/<key_id>         — revoke key
  GET    /tenants/<tenant_id>/metrics               — per-service aggregate stats
"""
import hashlib
import hmac
import ipaddress
import secrets
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import Blueprint, request, jsonify, abort

from db import get_connection, generate_id, is_valid_id

admin_bp = Blueprint("admin", __name__)

MAX_NAME_LEN = 100
MAX_URL_LEN = 2048
MAX_ALIAS_LEN = 64
PROXY_TIMEOUT = 10  # seconds — matches proxy route timeout cap

# Schemes that are safe to proxy
ALLOWED_SCHEMES = {"http", "https"}


# ---------------------------------------------------------------------------
# SSRF guard
# ---------------------------------------------------------------------------
def _is_safe_url(url: str) -> bool:
    """
    Return True if url is safe to use as a backend base_url.
    Rejects: non-http(s) schemes, unresolvable hosts, private/loopback/reserved IPs.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_SCHEMES:
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        infos = socket.getaddrinfo(hostname, None)
        if not infos:
            return False
        for _, _, _, _, sockaddr in infos:
            ip = ipaddress.ip_address(sockaddr[0])
            if (ip.is_loopback or ip.is_private or ip.is_link_local
                    or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
                return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# ID validation helper
# ---------------------------------------------------------------------------
def _require_valid_id(value: str, name: str = "id"):
    if not is_valid_id(value):
        abort(400, description=f"Invalid {name} format")


# ---------------------------------------------------------------------------
# POST /tenants
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants", methods=["POST"])
def create_tenant():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    if len(name) > MAX_NAME_LEN:
        return jsonify({"error": f"name too long (max {MAX_NAME_LEN})"}), 400

    tenant_id = generate_id()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO tenants (id, name) VALUES (?, ?)",
                (tenant_id, name),
            )
            conn.commit()
    except Exception as e:
        if "UNIQUE" in str(e):
            return jsonify({"error": "tenant name already exists"}), 409
        raise

    return jsonify({"tenant_id": tenant_id, "name": name}), 201


# ---------------------------------------------------------------------------
# GET /tenants
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants", methods=["GET"])
def list_tenants():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at FROM tenants ORDER BY created_at DESC"
        ).fetchall()
    return jsonify({"tenants": [dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# POST /tenants/<tenant_id>/services
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>/services", methods=["POST"])
def register_service(tenant_id):
    _require_valid_id(tenant_id, "tenant_id")
    with get_connection() as conn:
        tenant = conn.execute(
            "SELECT id FROM tenants WHERE id = ?", (tenant_id,)
        ).fetchone()
    if tenant is None:
        return jsonify({"error": "tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    alias = str(data.get("alias", "")).strip().lower()
    base_url = str(data.get("base_url", "")).strip()

    if not alias:
        return jsonify({"error": "alias is required"}), 400
    if len(alias) > MAX_ALIAS_LEN:
        return jsonify({"error": f"alias too long (max {MAX_ALIAS_LEN})"}), 400
    if not alias.replace("-", "").replace("_", "").isalnum():
        return jsonify({"error": "alias must be alphanumeric (hyphens/underscores allowed)"}), 400
    if not base_url:
        return jsonify({"error": "base_url is required"}), 400
    if len(base_url) > MAX_URL_LEN:
        return jsonify({"error": f"base_url too long (max {MAX_URL_LEN})"}), 400

    # SSRF check — must pass before storing
    if not _is_safe_url(base_url):
        return jsonify({"error": "base_url rejected: must use http/https and resolve to a public IP"}), 422

    service_id = generate_id()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO services (id, tenant_id, alias, base_url) VALUES (?, ?, ?, ?)",
                (service_id, tenant_id, alias, base_url),
            )
            conn.commit()
    except Exception as e:
        if "UNIQUE" in str(e):
            return jsonify({"error": "alias already registered for this tenant"}), 409
        raise

    return jsonify({
        "service_id": service_id,
        "tenant_id": tenant_id,
        "alias": alias,
        "base_url": base_url,
    }), 201


# ---------------------------------------------------------------------------
# GET /tenants/<tenant_id>/services
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>/services", methods=["GET"])
def list_services(tenant_id):
    _require_valid_id(tenant_id, "tenant_id")
    with get_connection() as conn:
        tenant = conn.execute("SELECT id FROM tenants WHERE id=?", (tenant_id,)).fetchone()
        if tenant is None:
            return jsonify({"error": "tenant not found"}), 404
        rows = conn.execute(
            "SELECT id, alias, base_url, created_at FROM services WHERE tenant_id=? ORDER BY created_at DESC",
            (tenant_id,),
        ).fetchall()
    return jsonify({"services": [dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# DELETE /tenants/<tenant_id>/services/<service_id>
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>/services/<service_id>", methods=["DELETE"])
def delete_service(tenant_id, service_id):
    _require_valid_id(tenant_id, "tenant_id")
    _require_valid_id(service_id, "service_id")
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM services WHERE id=? AND tenant_id=?",
            (service_id, tenant_id),
        )
        conn.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "service not found"}), 404
    return jsonify({"deleted": service_id}), 200


# ---------------------------------------------------------------------------
# POST /tenants/<tenant_id>/keys
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>/keys", methods=["POST"])
def create_key(tenant_id):
    _require_valid_id(tenant_id, "tenant_id")
    with get_connection() as conn:
        tenant = conn.execute("SELECT id FROM tenants WHERE id=?", (tenant_id,)).fetchone()
    if tenant is None:
        return jsonify({"error": "tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:MAX_NAME_LEN]
    expires_at = data.get("expires_at")  # ISO8601 string or None

    # Generate key
    plaintext = secrets.token_urlsafe(32)
    key_prefix = plaintext[:16]
    salt = secrets.token_hex(16)
    key_hash = hashlib.sha256((salt + plaintext).encode()).hexdigest()
    key_id = generate_id()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO api_keys (id, tenant_id, name, key_prefix, key_salt, key_hash, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (key_id, tenant_id, name, key_prefix, salt, key_hash, expires_at),
        )
        conn.commit()

    return jsonify({
        "key_id": key_id,
        "tenant_id": tenant_id,
        "name": name,
        "key": plaintext,  # returned once, never stored in plaintext
        "expires_at": expires_at,
    }), 201


# ---------------------------------------------------------------------------
# GET /tenants/<tenant_id>/keys
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>/keys", methods=["GET"])
def list_keys(tenant_id):
    _require_valid_id(tenant_id, "tenant_id")
    with get_connection() as conn:
        tenant = conn.execute("SELECT id FROM tenants WHERE id=?", (tenant_id,)).fetchone()
        if tenant is None:
            return jsonify({"error": "tenant not found"}), 404
        rows = conn.execute(
            """
            SELECT id, name, key_prefix, status, expires_at, created_at
            FROM api_keys WHERE tenant_id=? ORDER BY created_at DESC
            """,
            (tenant_id,),
        ).fetchall()
    return jsonify({"keys": [dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# DELETE /tenants/<tenant_id>/keys/<key_id>
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>/keys/<key_id>", methods=["DELETE"])
def revoke_key(tenant_id, key_id):
    _require_valid_id(tenant_id, "tenant_id")
    _require_valid_id(key_id, "key_id")
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE api_keys SET status='revoked' WHERE id=? AND tenant_id=?",
            (key_id, tenant_id),
        )
        conn.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "key not found"}), 404
    return jsonify({"revoked": key_id}), 200


# ---------------------------------------------------------------------------
# GET /tenants/<tenant_id>/metrics
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>/metrics", methods=["GET"])
def get_metrics(tenant_id):
    _require_valid_id(tenant_id, "tenant_id")
    with get_connection() as conn:
        tenant = conn.execute("SELECT id FROM tenants WHERE id=?", (tenant_id,)).fetchone()
        if tenant is None:
            return jsonify({"error": "tenant not found"}), 404

        since = request.args.get("since", "")
        service_filter = request.args.get("service_id", "")

        # Default: last 24 hours
        if not since:
            since = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            # SQLite datetime math for 24h ago
            since_clause = "AND rl.created_at >= datetime('now', '-1 day')"
            params = [tenant_id]
        else:
            since_clause = "AND rl.created_at >= ?"
            params = [tenant_id, since]

        service_clause = ""
        if service_filter and is_valid_id(service_filter):
            service_clause = "AND rl.service_id = ?"
            params.append(service_filter)

        rows = conn.execute(
            f"""
            SELECT
                s.id AS service_id,
                s.alias,
                COUNT(*) AS total_requests,
                SUM(CASE WHEN rl.status_code < 400 THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN rl.status_code >= 400 OR rl.error_message IS NOT NULL THEN 1 ELSE 0 END) AS error_count,
                AVG(rl.latency_ms) AS avg_latency_ms
            FROM request_logs rl
            JOIN services s ON s.id = rl.service_id
            WHERE rl.tenant_id = ?
              {since_clause}
              {service_clause}
            GROUP BY rl.service_id, s.alias
            ORDER BY total_requests DESC
            """,
            params,
        ).fetchall()

        # P95 computation: fetch raw latencies per service and compute in Python
        # (SQLite doesn't have percentile functions)
        service_ids = [r["service_id"] for r in rows]
        p95_map = {}
        for sid in service_ids:
            lat_rows = conn.execute(
                f"""
                SELECT latency_ms FROM request_logs
                WHERE tenant_id=? AND service_id=? AND latency_ms IS NOT NULL
                  {since_clause if not since else "AND created_at >= ?"}
                ORDER BY latency_ms
                """,
                [tenant_id, sid] + ([since] if since else []),
            ).fetchall()
            lats = [r["latency_ms"] for r in lat_rows]
            if lats:
                idx = max(0, int(len(lats) * 0.95) - 1)
                p95_map[sid] = lats[idx]
            else:
                p95_map[sid] = None

    services_out = []
    for r in rows:
        sid = r["service_id"]
        services_out.append({
            "service_id": sid,
            "alias": r["alias"],
            "total_requests": r["total_requests"],
            "success_count": r["success_count"] or 0,
            "error_count": r["error_count"] or 0,
            "avg_latency_ms": round(r["avg_latency_ms"], 1) if r["avg_latency_ms"] else None,
            "p95_latency_ms": p95_map.get(sid),
        })

    return jsonify({
        "tenant_id": tenant_id,
        "services": services_out,
    })
