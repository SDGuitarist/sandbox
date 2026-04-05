import json
import uuid

from .db import _now


def create_service(conn, name: str, health_check_url: str, url: str = None,
                   description: str = None) -> dict:
    """Create a service. Raises sqlite3.IntegrityError on duplicate name."""
    service_id = str(uuid.uuid4())
    now = _now()
    conn.execute(
        """INSERT INTO services (id, name, url, health_check_url, description, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (service_id, name, url, health_check_url, description, now),
    )
    row = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    return dict(row)


def get_service(conn, service_id: str) -> dict | None:
    """Return service dict or None."""
    row = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    return dict(row) if row else None


def list_services(conn) -> list[dict]:
    """Return all services ordered by name."""
    rows = conn.execute("SELECT * FROM services ORDER BY name ASC").fetchall()
    return [dict(r) for r in rows]


def delete_service(conn, service_id: str) -> bool:
    """Delete a service and cascade to related records. Returns True if deleted."""
    cursor = conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
    return cursor.rowcount > 0


def get_dashboard(conn) -> list[dict]:
    """Return all services with their latest health status.

    Uses a correlated subquery to find the most recent health result per service.
    Returns status=None if a service has never been checked.
    """
    rows = conn.execute(
        """SELECT s.*,
                  h.status        AS health_status,
                  h.checked_at    AS last_checked_at,
                  h.response_time_ms AS last_response_ms,
                  h.status_code   AS last_status_code
           FROM services s
           LEFT JOIN health_results h ON h.id = (
               SELECT id FROM health_results
               WHERE service_id = s.id
               ORDER BY id DESC LIMIT 1
           )
           ORDER BY s.name ASC"""
    ).fetchall()
    return [dict(r) for r in rows]
