"""
Flask route handlers for the distributed task scheduler.

Endpoints:
  POST   /schedules          — create a new schedule
  GET    /schedules          — list all schedules
  GET    /schedules/<id>     — get schedule + recent job_runs
  PATCH  /schedules/<id>     — update status (active/paused/deleted)
  GET    /dashboard          — upcoming / overdue / completed summary
"""
from flask import Blueprint, request, jsonify
from croniter import croniter, CroniterBadCronError
from datetime import datetime, timezone
from db import get_connection

bp = Blueprint("scheduler", __name__)


def _next_run_at(cron_expr: str, base: datetime | None = None) -> str:
    """
    Compute the next ISO-8601 UTC datetime string after `base` (default: now)
    for the given cron expression.
    """
    if base is None:
        base = datetime.now(timezone.utc)
    # croniter works with naive datetimes; strip tzinfo
    base_naive = base.replace(tzinfo=None)
    cron = croniter(cron_expr, base_naive)
    next_dt = cron.get_next(datetime)
    return next_dt.strftime("%Y-%m-%d %H:%M:%S")


def _validate_cron(cron_expr: str) -> str | None:
    """Return error message if cron_expr is invalid, else None."""
    try:
        croniter(cron_expr)
        return None
    except (CroniterBadCronError, ValueError) as e:
        return str(e)


# ---------------------------------------------------------------------------
# POST /schedules
# ---------------------------------------------------------------------------
@bp.route("/schedules", methods=["POST"])
def create_schedule():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    cron_expr = data.get("cron_expr", "").strip()
    payload = data.get("payload", {})

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not cron_expr:
        return jsonify({"error": "cron_expr is required"}), 400

    err = _validate_cron(cron_expr)
    if err:
        return jsonify({"error": f"invalid cron_expr: {err}"}), 400

    import json
    payload_str = json.dumps(payload)
    next_run = _next_run_at(cron_expr)

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO schedules (name, cron_expr, payload, next_run_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, cron_expr, payload_str, next_run),
        )
        schedule_id = cur.lastrowid
        conn.commit()

    return jsonify({
        "id": schedule_id,
        "name": name,
        "cron_expr": cron_expr,
        "status": "active",
        "next_run_at": next_run,
    }), 201


# ---------------------------------------------------------------------------
# GET /schedules
# ---------------------------------------------------------------------------
@bp.route("/schedules", methods=["GET"])
def list_schedules():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, cron_expr, status, next_run_at, created_at FROM schedules ORDER BY id"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# GET /schedules/<id>
# ---------------------------------------------------------------------------
@bp.route("/schedules/<int:schedule_id>", methods=["GET"])
def get_schedule(schedule_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "not found"}), 404
        runs = conn.execute(
            """
            SELECT id, status, created_at, claimed_at, completed_at, result
            FROM job_runs
            WHERE schedule_id = ?
            ORDER BY id DESC LIMIT 20
            """,
            (schedule_id,),
        ).fetchall()
    return jsonify({
        "schedule": dict(row),
        "recent_runs": [dict(r) for r in runs],
    })


# ---------------------------------------------------------------------------
# PATCH /schedules/<id>
# ---------------------------------------------------------------------------
@bp.route("/schedules/<int:schedule_id>", methods=["PATCH"])
def update_schedule(schedule_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status", "").strip()

    allowed = {"active", "paused", "deleted"}
    if new_status not in allowed:
        return jsonify({"error": f"status must be one of {sorted(allowed)}"}), 400

    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE schedules SET status = ? WHERE id = ?",
            (new_status, schedule_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "not found"}), 404

    return jsonify({"id": schedule_id, "status": new_status})


# ---------------------------------------------------------------------------
# GET /dashboard
# ---------------------------------------------------------------------------
@bp.route("/dashboard", methods=["GET"])
def dashboard():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        # Upcoming: next 10 fires across active schedules
        upcoming_rows = conn.execute(
            """
            SELECT id, name, cron_expr, next_run_at
            FROM schedules
            WHERE status = 'active'
            ORDER BY next_run_at ASC
            LIMIT 10
            """,
        ).fetchall()

        # Overdue: active schedules past their next_run_at with no pending/running run
        overdue_rows = conn.execute(
            """
            SELECT s.id, s.name, s.cron_expr, s.next_run_at
            FROM schedules s
            WHERE s.status = 'active'
              AND s.next_run_at < ?
              AND NOT EXISTS (
                  SELECT 1 FROM job_runs jr
                  WHERE jr.schedule_id = s.id
                    AND jr.status IN ('pending', 'running')
              )
            ORDER BY s.next_run_at ASC
            """,
            (now,),
        ).fetchall()

        # Completed: last 20 completed job_runs
        completed_rows = conn.execute(
            """
            SELECT jr.id, jr.schedule_id, s.name AS schedule_name,
                   jr.status, jr.completed_at, jr.result
            FROM job_runs jr
            JOIN schedules s ON s.id = jr.schedule_id
            WHERE jr.status = 'completed'
            ORDER BY jr.completed_at DESC
            LIMIT 20
            """,
        ).fetchall()

    return jsonify({
        "upcoming": [dict(r) for r in upcoming_rows],
        "overdue": [dict(r) for r in overdue_rows],
        "completed": [dict(r) for r in completed_rows],
    })
