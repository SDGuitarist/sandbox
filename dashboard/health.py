import json
from datetime import datetime, timezone

from .db import _now


def record_result(conn, service_id: str, status: str, status_code=None,
                  response_time_ms=None, error_message=None) -> dict:
    """Record a health check result."""
    now = _now()
    conn.execute(
        """INSERT INTO health_results
           (service_id, checked_at, status, status_code, response_time_ms, error_message)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (service_id, now, status, status_code, response_time_ms, error_message),
    )
    row = conn.execute(
        "SELECT * FROM health_results WHERE id = last_insert_rowid()"
    ).fetchone()
    return dict(row)


def get_latest_status(conn, service_id: str) -> dict | None:
    """Return the most recent health result for a service, or None."""
    row = conn.execute(
        """SELECT * FROM health_results WHERE service_id = ?
           ORDER BY id DESC LIMIT 1""",
        (service_id,),
    ).fetchone()
    return dict(row) if row else None


def list_results(conn, service_id: str, limit: int = 20) -> list[dict]:
    """Return up to `limit` most recent results for a service."""
    limit = max(1, min(int(limit), 200))
    rows = conn.execute(
        """SELECT * FROM health_results WHERE service_id = ?
           ORDER BY id DESC LIMIT ?""",
        (service_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]
