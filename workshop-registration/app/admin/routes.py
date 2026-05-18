import base64
import csv
import hmac
import io
import os
import time
from collections import defaultdict
from flask import Blueprint, Response, jsonify, make_response, request
from app import limiter
from app.db import get_db

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

_WWW_AUTH = 'Basic realm="Workshop Admin"'

# Brute-force protection: track failed auth attempts per IP
_failed_attempts = defaultdict(list)
_MAX_FAILURES = 5
_WINDOW_SECONDS = 60


def _is_locked_out(ip):
    now = time.time()
    attempts = _failed_attempts[ip]
    _failed_attempts[ip] = [t for t in attempts if now - t < _WINDOW_SECONDS]
    return len(_failed_attempts[ip]) >= _MAX_FAILURES


def _record_failure(ip):
    _failed_attempts[ip].append(time.time())


def require_admin(req):
    ip = req.remote_addr or "unknown"
    if _is_locked_out(ip):
        resp = make_response(
            jsonify({"error": "Too many failed attempts, try again later", "code": "UNAUTHORIZED"}), 429
        )
        resp.headers["Retry-After"] = str(_WINDOW_SECONDS)
        return resp

    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Basic "):
        resp = make_response(
            jsonify({"error": "Authentication required", "code": "UNAUTHORIZED"}), 401
        )
        resp.headers["WWW-Authenticate"] = _WWW_AUTH
        return resp

    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        _, password = decoded.split(":", 1)
    except Exception:
        _record_failure(ip)
        resp = make_response(
            jsonify({"error": "Invalid credentials", "code": "UNAUTHORIZED"}), 401
        )
        resp.headers["WWW-Authenticate"] = _WWW_AUTH
        return resp

    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_password or not hmac.compare_digest(password, admin_password):
        _record_failure(ip)
        resp = make_response(
            jsonify({"error": "Invalid credentials", "code": "UNAUTHORIZED"}), 401
        )
        resp.headers["WWW-Authenticate"] = _WWW_AUTH
        return resp

    return None


@admin_bp.route("/registrants")
@limiter.limit("10 per minute")
def list_registrants():
    auth_error = require_admin(request)
    if auth_error:
        return auth_error

    capacity = int(os.environ.get("WORKSHOP_CAPACITY", 35))

    with get_db() as conn:
        rows = conn.execute("SELECT * FROM registrants ORDER BY id").fetchall()

    registrants = []
    counts = {"paid": 0, "waitlisted": 0, "pending_payment": 0, "cancelled": 0, "payment_failed": 0}
    for row in rows:
        registrant = {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "role": row["role"],
            "status": row["status"],
            "queue_position": row["queue_position"],
            "square_order_id": row["square_order_id"],
            "square_payment_id": row["square_payment_id"],
            "created_at": row["created_at"],
            "paid_at": row["paid_at"],
        }
        registrants.append(registrant)
        status = row["status"]
        if status in counts:
            counts[status] += 1

    return jsonify({
        "registrants": registrants,
        "total": len(registrants),
        "capacity": capacity,
        "paid_count": counts["paid"],
        "waitlist_count": counts["waitlisted"],
        "pending_count": counts["pending_payment"],
        "cancelled_count": counts["cancelled"],
        "payment_failed_count": counts["payment_failed"],
    })


@admin_bp.route("/stats")
@limiter.limit("10 per minute")
def stats():
    auth_error = require_admin(request)
    if auth_error:
        return auth_error

    with get_db() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM registrants GROUP BY status"
        ).fetchall()

    counts = {
        "total": 0,
        "paid": 0,
        "waitlisted": 0,
        "cancelled": 0,
        "pending_payment": 0,
        "payment_failed": 0,
    }
    for row in rows:
        status = row["status"]
        count = row["cnt"]
        if status in counts:
            counts[status] = count
        counts["total"] += count

    return jsonify(counts)


@admin_bp.route("/export")
@limiter.limit("10 per minute")
def export_csv():
    auth_error = require_admin(request)
    if auth_error:
        return auth_error

    with get_db() as conn:
        rows = conn.execute("SELECT * FROM registrants ORDER BY id").fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "name", "email", "role", "status", "queue_position",
        "square_order_id", "square_payment_id", "created_at", "paid_at",
    ])
    for row in rows:
        writer.writerow([
            row["id"], row["name"], row["email"], row["role"],
            row["status"], row["queue_position"], row["square_order_id"],
            row["square_payment_id"], row["created_at"], row["paid_at"],
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=registrants.csv"},
    )
