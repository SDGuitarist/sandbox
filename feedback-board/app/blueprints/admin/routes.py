import base64
import csv
import hmac
import io
import os
import time
from collections import defaultdict

from flask import Response, flash, make_response, redirect, render_template, request, url_for

from app.blueprints.admin import admin_bp
from app.db import get_db
from app.models import (
    VALID_CATEGORIES,
    VALID_STATUSES,
    get_all_feedback_admin,
    get_feedback_stats,
    update_feedback_status,
)

_WWW_AUTH = 'Basic realm="Feedback Admin"'

# Brute-force protection
_failed_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_FAILURES = 5
_WINDOW_SECONDS = 60
_MAX_TRACKED_IPS = 10000


def _is_locked_out(ip: str) -> bool:
    now = time.time()
    attempts = _failed_attempts[ip]
    _failed_attempts[ip] = [t for t in attempts if now - t < _WINDOW_SECONDS]
    return len(_failed_attempts[ip]) >= _MAX_FAILURES


def _record_failure(ip: str) -> None:
    if len(_failed_attempts) >= _MAX_TRACKED_IPS:
        oldest_ip = min(_failed_attempts, key=lambda k: _failed_attempts[k][-1] if _failed_attempts[k] else 0)
        del _failed_attempts[oldest_ip]
    _failed_attempts[ip].append(time.time())


def _require_admin():
    ip = request.remote_addr or "unknown"
    if _is_locked_out(ip):
        resp = make_response("Too many failed attempts, try again later", 429)
        resp.headers["Retry-After"] = str(_WINDOW_SECONDS)
        return resp

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Basic "):
        resp = make_response("Authentication required", 401)
        resp.headers["WWW-Authenticate"] = _WWW_AUTH
        return resp

    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        _, password = decoded.split(":", 1)
    except Exception:
        _record_failure(ip)
        resp = make_response("Invalid credentials", 401)
        resp.headers["WWW-Authenticate"] = _WWW_AUTH
        return resp

    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_password or not hmac.compare_digest(password, admin_password):
        _record_failure(ip)
        resp = make_response("Invalid credentials", 401)
        resp.headers["WWW-Authenticate"] = _WWW_AUTH
        return resp

    return None


@admin_bp.before_request
def check_admin_auth():
    error_response = _require_admin()
    if error_response:
        return error_response


@admin_bp.route("/")
def dashboard():
    status_filter = request.args.get("status")
    category_filter = request.args.get("category")

    with get_db() as conn:
        items = get_all_feedback_admin(conn, status=status_filter, category=category_filter)
        stats = get_feedback_stats(conn)

    return render_template(
        "admin/dashboard.html",
        feedback_items=items,
        stats=stats,
        categories=VALID_CATEGORIES,
        statuses=VALID_STATUSES,
        current_status=status_filter,
        current_category=category_filter,
    )


@admin_bp.route("/status/<int:feedback_id>", methods=["POST"])
def update_status(feedback_id):
    new_status = (request.form.get("status") or "").strip()
    if new_status not in VALID_STATUSES:
        flash("Invalid status", "error")
        return _redirect_preserving_filters()

    with get_db(immediate=True) as conn:
        updated = update_feedback_status(conn, feedback_id, new_status)
        if not updated:
            flash("Feedback item not found", "error")

    return _redirect_preserving_filters()


@admin_bp.route("/export")
def export_csv():
    with get_db() as conn:
        rows = get_all_feedback_admin(conn)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "title", "description", "category", "status",
                     "vote_count", "created_at", "updated_at"])
    for row in rows:
        writer.writerow([
            row["id"],
            _sanitize_csv(row["title"]),
            _sanitize_csv(row["description"]),
            row["category"],
            row["status"],
            row["vote_count"],
            row["created_at"],
            row["updated_at"],
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=feedback-export.csv"},
    )


def _sanitize_csv(value: str) -> str:
    """Prevent formula injection in spreadsheets."""
    if not value:
        return value
    value = value.replace("\x00", "")
    stripped = value.strip()
    if stripped and stripped[0] in "=-+@|\t\r\n":
        return "'" + value
    return value


def _redirect_preserving_filters():
    """Redirect back to dashboard preserving any active filters."""
    args = {}
    status = request.args.get("status") or request.form.get("current_status")
    category = request.args.get("category") or request.form.get("current_category")
    if status:
        args["status"] = status
    if category:
        args["category"] = category
    return redirect(url_for("admin.dashboard", **args))
