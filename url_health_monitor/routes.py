"""
Flask route handlers for the URL health monitor.

Endpoints:
  POST   /urls          — register a URL to monitor
  GET    /urls          — list all active monitored URLs
  GET    /urls/<id>     — URL details + last 10 check_results
  DELETE /urls/<id>     — soft-delete a monitored URL
  GET    /alerts        — return URLs with current_status='degraded'
"""
import ipaddress
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse
from flask import Blueprint, request, jsonify
from db import get_connection

bp = Blueprint("health_monitor", __name__)

MAX_NAME_LEN = 255
MAX_URL_LEN = 2048
MAX_CHECK_INTERVAL = 86400   # 1 day
MAX_FAILURE_THRESHOLD = 100
MAX_TIMEOUT_SECONDS = 30


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _is_safe_host(hostname: str) -> bool:
    """
    Resolve hostname and reject private/loopback/link-local/reserved addresses.
    Prevents SSRF attacks targeting internal network services.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False  # unresolvable — reject
    for _, _, _, _, sockaddr in infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            return False
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return bool(infos)  # reject if no addresses resolved


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# POST /urls
# ---------------------------------------------------------------------------
@bp.route("/urls", methods=["POST"])
def register_url():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400

    url = data.get("url", "")
    if not isinstance(url, str) or not url.strip():
        return jsonify({"error": "url is required"}), 400
    url = url.strip()
    if len(url) > MAX_URL_LEN:
        return jsonify({"error": f"url must be {MAX_URL_LEN} characters or fewer"}), 400
    if not _is_valid_url(url):
        return jsonify({"error": "url must be a valid http or https URL"}), 400

    # SSRF protection: reject private/loopback/link-local hosts
    hostname = urlparse(url).hostname or ""
    if not _is_safe_host(hostname):
        return jsonify({"error": "url resolves to a private or reserved address"}), 400

    name = data.get("name", "")
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name is required"}), 400
    name = name.strip()
    if len(name) > MAX_NAME_LEN:
        return jsonify({"error": f"name must be {MAX_NAME_LEN} characters or fewer"}), 400

    check_interval = data.get("check_interval_seconds", 300)
    if not isinstance(check_interval, int) or not (10 <= check_interval <= MAX_CHECK_INTERVAL):
        return jsonify({"error": f"check_interval_seconds must be between 10 and {MAX_CHECK_INTERVAL}"}), 400

    failure_threshold = data.get("failure_threshold", 1)
    if not isinstance(failure_threshold, int) or not (1 <= failure_threshold <= MAX_FAILURE_THRESHOLD):
        return jsonify({"error": f"failure_threshold must be between 1 and {MAX_FAILURE_THRESHOLD}"}), 400

    timeout_seconds = data.get("timeout_seconds", 10)
    if not isinstance(timeout_seconds, int) or not (1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS):
        return jsonify({"error": f"timeout_seconds must be between 1 and {MAX_TIMEOUT_SECONDS}"}), 400

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO monitored_urls
                (url, name, check_interval_seconds, failure_threshold, timeout_seconds)
            VALUES (?, ?, ?, ?, ?)
            """,
            (url, name, check_interval, failure_threshold, timeout_seconds),
        )
        url_id = cur.lastrowid
        conn.commit()

    return jsonify({
        "id": url_id,
        "url": url,
        "name": name,
        "check_interval_seconds": check_interval,
        "failure_threshold": failure_threshold,
        "timeout_seconds": timeout_seconds,
        "current_status": "unknown",
    }), 201


# ---------------------------------------------------------------------------
# GET /urls
# ---------------------------------------------------------------------------
@bp.route("/urls", methods=["GET"])
def list_urls():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, url, name, check_interval_seconds, failure_threshold,
                   timeout_seconds, current_status, last_checked_at, created_at
            FROM monitored_urls
            WHERE current_status != 'deleted'
            ORDER BY id
            """
        ).fetchall()
    return jsonify({"urls": [dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# GET /urls/<id>
# ---------------------------------------------------------------------------
@bp.route("/urls/<int:url_id>", methods=["GET"])
def get_url(url_id):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, url, name, check_interval_seconds, failure_threshold,
                   timeout_seconds, current_status, last_checked_at, created_at
            FROM monitored_urls WHERE id = ? AND current_status != 'deleted'
            """,
            (url_id,),
        ).fetchone()
        if row is None:
            return jsonify({"error": "not found"}), 404

        results = conn.execute(
            """
            SELECT id, job_id, http_status_code, response_time_ms,
                   error_message, checked_at
            FROM check_results
            WHERE url_id = ?
            ORDER BY checked_at DESC, id DESC LIMIT 10
            """,
            (url_id,),
        ).fetchall()

    return jsonify({
        "url": dict(row),
        "recent_results": [dict(r) for r in results],
    })


# ---------------------------------------------------------------------------
# DELETE /urls/<id>
# ---------------------------------------------------------------------------
@bp.route("/urls/<int:url_id>", methods=["DELETE"])
def delete_url(url_id):
    now = _now_str()
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE monitored_urls SET current_status = 'deleted' WHERE id = ? AND current_status != 'deleted'",
            (url_id,),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "not found or already deleted"}), 404
        # Cancel any pending/running jobs for this URL so they don't execute after deletion
        conn.execute(
            "UPDATE check_jobs SET status='failed', completed_at=? WHERE url_id=? AND status IN ('pending','running')",
            (now, url_id),
        )
        conn.commit()
    return jsonify({"id": url_id, "current_status": "deleted"}), 200


# ---------------------------------------------------------------------------
# GET /alerts
# ---------------------------------------------------------------------------
@bp.route("/alerts", methods=["GET"])
def alerts():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.url, u.name, u.current_status, u.last_checked_at,
                   cr.http_status_code, cr.response_time_ms, cr.error_message,
                   cr.checked_at AS last_check_at
            FROM monitored_urls u
            LEFT JOIN check_results cr ON cr.id = (
                SELECT id FROM check_results
                WHERE url_id = u.id
                ORDER BY checked_at DESC, id DESC LIMIT 1
            )
            WHERE u.current_status = 'degraded'
            ORDER BY u.id
            """
        ).fetchall()
    return jsonify({"alerts": [dict(r) for r in rows]})
