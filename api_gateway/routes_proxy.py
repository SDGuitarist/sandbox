"""
Proxy route for the API gateway.

Endpoint: ANY /proxy/<alias>/<path:remainder>

Flow:
  1. Extract Bearer token from Authorization header
  2. Lookup by key_prefix (first 16 chars), verify SHA-256 hash, check status + expiry
  3. Resolve tenant from key row
  4. Lookup service by (tenant_id, alias)
  5. Forward request to base_url/<remainder>?<query_string>
  6. Stream upstream response back to caller (upstream connection closed via generator finally)
  7. Log latency (time-to-first-byte) + status to request_logs
"""
import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

import requests as req_lib
from flask import Blueprint, request, Response, stream_with_context, jsonify

from db import get_connection, generate_id, PROXY_TIMEOUT

proxy_bp = Blueprint("proxy", __name__)

CHUNK_SIZE = 8192

log = logging.getLogger(__name__)

# Headers NOT forwarded from client to upstream
_HOP_BY_HOP = {
    "host", "authorization", "content-length", "transfer-encoding",
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "upgrade",
    # Prevent spoofing of gateway-controlled routing headers
    "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto",
    "x-real-ip", "x-original-url",
}

# Headers NOT forwarded from upstream to client
_UPSTREAM_STRIP = {
    "transfer-encoding", "connection", "keep-alive",
    "proxy-authenticate", "proxy-authorization",
}

# Maximum header value length — reject oversized values
_MAX_HEADER_VALUE_LEN = 8192


def _safe_forward_headers(incoming_headers: dict) -> dict:
    """
    Return a filtered copy of request headers safe to forward upstream.
    Strips hop-by-hop headers, proxy-spoofing headers, and CRLF injection attempts.
    """
    result = {}
    for k, v in incoming_headers.items():
        if k.lower() in _HOP_BY_HOP:
            continue
        # Reject CRLF injection in header values
        if '\r' in v or '\n' in v or '\0' in v:
            continue
        # Skip oversized header values
        if len(v) > _MAX_HEADER_VALUE_LEN:
            continue
        result[k] = v
    return result


def _safe_response_headers(upstream_headers) -> dict:
    """Return a filtered copy of upstream response headers safe to return to client."""
    return {
        k: v for k, v in upstream_headers.items()
        if k.lower() not in _UPSTREAM_STRIP
    }


def _verify_api_key(submitted_key: str):
    """
    Look up API key by prefix, verify hash, check status and expiry.
    Returns the key row dict on success, None on failure.
    Iterates all rows with matching prefix so a prefix collision doesn't block a valid key.
    """
    if not submitted_key or len(submitted_key) < 16:
        return None
    key_prefix = submitted_key[:16]

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM api_keys WHERE key_prefix = ? AND status = 'active'",
            (key_prefix,),
        ).fetchall()

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    for row in rows:
        candidate_hash = hashlib.sha256(
            (row["key_salt"] + submitted_key).encode()
        ).hexdigest()
        if hmac.compare_digest(candidate_hash, row["key_hash"]):
            # Check expiry — use continue (not return None) so prefix collision doesn't block valid sibling keys
            if row["expires_at"] and row["expires_at"] < now_str:
                continue
            return dict(row)
    return None


def _log_request(tenant_id, service_id, key_id, method, path,
                 status_code, latency_ms, error_message=None):
    """Write one row to request_logs. Failures are logged but never raise."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO request_logs
                    (tenant_id, service_id, api_key_id, method, path,
                     status_code, latency_ms, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (tenant_id, service_id, key_id, method, path,
                 status_code, latency_ms, error_message),
            )
            conn.commit()
    except Exception as exc:
        log.warning("request_logs write failed: %s", exc)


@proxy_bp.route("/proxy/<alias>", defaults={"remainder": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@proxy_bp.route("/proxy/<alias>/<path:remainder>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def proxy(alias, remainder):
    # 1. Extract API key
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "missing or invalid Authorization header"}), 401

    submitted_key = auth_header[len("Bearer "):]
    key_row = _verify_api_key(submitted_key)
    if key_row is None:
        return jsonify({"error": "invalid or expired API key"}), 401

    tenant_id = key_row["tenant_id"]
    key_id = key_row["id"]

    # 2. Resolve service by alias within tenant
    with get_connection() as conn:
        service = conn.execute(
            "SELECT id, base_url FROM services WHERE tenant_id=? AND alias=?",
            (tenant_id, alias.lower()),
        ).fetchone()

    if service is None:
        # Generic 404 — do not confirm alias existence to unauthenticated callers
        return jsonify({"error": "not found"}), 404

    service_id = service["id"]
    base_url = service["base_url"].rstrip("/")

    # 3. Build target URL — handle base_url that already contains a query string
    path_part = remainder.strip("/")
    target_path = f"{base_url}/{path_part}" if path_part else base_url

    # Append query string only if present, avoiding double-?
    query_string = urlencode(request.args, doseq=True)
    if query_string:
        separator = "&" if "?" in target_path else "?"
        target_url = f"{target_path}{separator}{query_string}"
    else:
        target_url = target_path

    # 4. Forward request
    forward_headers = _safe_forward_headers(dict(request.headers))
    body = request.get_data()

    start_time = time.monotonic()
    error_message = None
    status_code = None

    try:
        upstream = req_lib.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            data=body if body else None,
            stream=True,
            allow_redirects=False,  # SSRF defense — never follow redirects
            timeout=PROXY_TIMEOUT,
        )
        status_code = upstream.status_code
        latency_ms = int((time.monotonic() - start_time) * 1000)  # time-to-first-byte

        # Extract content-type before building response to avoid Flask default override
        upstream_content_type = upstream.headers.get("content-type", "application/octet-stream")
        response_headers = _safe_response_headers(upstream.headers)
        # Remove content-type from response_headers dict since we pass it explicitly
        response_headers.pop("content-type", None)
        response_headers.pop("Content-Type", None)

        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()  # always close upstream connection

        _log_request(tenant_id, service_id, key_id, request.method,
                     f"/{alias}/{remainder}", status_code, latency_ms)

        return Response(
            stream_with_context(generate()),
            status=status_code,
            headers=response_headers,
            content_type=upstream_content_type,
        )

    except req_lib.exceptions.Timeout:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        error_message = "upstream timeout"
        _log_request(tenant_id, service_id, key_id, request.method,
                     f"/{alias}/{remainder}", None, latency_ms, error_message)
        return jsonify({"error": "upstream request timed out"}), 504

    except req_lib.exceptions.ConnectionError:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        error_message = "connection error"  # do not store raw exception string (may leak internal hostnames)
        log.warning("Proxy ConnectionError for %s/%s", alias, remainder)
        _log_request(tenant_id, service_id, key_id, request.method,
                     f"/{alias}/{remainder}", None, latency_ms, error_message)
        return jsonify({"error": "could not connect to upstream service"}), 502

    except Exception as exc:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        error_message = "gateway error"
        log.exception("Unexpected proxy error for %s/%s: %s", alias, remainder, exc)
        _log_request(tenant_id, service_id, key_id, request.method,
                     f"/{alias}/{remainder}", None, latency_ms, error_message)
        return jsonify({"error": "gateway error"}), 500
