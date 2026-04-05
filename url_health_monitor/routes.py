"""
Flask route handlers for the URL health monitor.

Endpoints:
  POST   /urls          — register a URL to monitor
  GET    /urls          — list all active monitored URLs
  GET    /urls/<id>     — URL details + last 10 check_results
  DELETE /urls/<id>     — soft-delete a monitored URL
  GET    /alerts        — return URLs with current_status='degraded'
"""
import json
from urllib.parse import urlparse
from flask import Blueprint, request, jsonify
from db import get_connection

bp = Blueprint("health_monitor", __name__)

MAX_NAME_LEN = 255
MAX_URL_LEN = 2048


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


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

    name = data.get("name", "")
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name is required"}), 400
    name = name.strip()
    if len(name) > MAX_NAME_LEN:
        return jsonify({"error": f"name must be {MAX_NAME_LEN} characters or fewer"}), 400

    check_interval = data.get("check_interval_seconds", 300)
    if not isinstance(check_interval, int) or check_interval < 10:
        return jsonify({"error": "check_interval_seconds must be an integer >= 10"}), 400

    failure_threshold = data.get("failure_threshold", 1)
    if not isinstance(failure_threshold, int) or failure_threshold < 1:
        return jsonify({"error": "failure_threshold must be an integer >= 1"}), 400

    timeout_seconds = data.get("timeout_seconds", 10)
    if not isinstance(timeout_seconds, int) or timeout_seconds < 1:
        return jsonify({"error": "timeout_seconds must be an integer >= 1"}), 400

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
            FROM monitored_urls WHERE id = ?
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
            ORDER BY checked_at DESC LIMIT 10
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
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE monitored_urls SET current_status = 'deleted' WHERE id = ? AND current_status != 'deleted'",
            (url_id,),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "not found or already deleted"}), 404
        conn.commit()
    return jsonify({"id": url_id, "current_status": "deleted"})


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
                ORDER BY checked_at DESC LIMIT 1
            )
            WHERE u.current_status = 'degraded'
            ORDER BY u.id
            """
        ).fetchall()
    return jsonify({"alerts": [dict(r) for r in rows]})
