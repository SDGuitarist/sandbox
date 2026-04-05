import uuid

from .db import _now


def enqueue_job(conn, service_id: str, scheduled_at: str = None) -> dict:
    """Enqueue a health check job for a service."""
    now = _now()
    conn.execute(
        """INSERT INTO health_jobs (service_id, status, scheduled_at)
           VALUES (?, 'pending', ?)""",
        (service_id, scheduled_at or now),
    )
    row = conn.execute(
        "SELECT * FROM health_jobs WHERE id = last_insert_rowid()"
    ).fetchone()
    return dict(row)


def claim_job(conn, worker_id: str) -> dict | None:
    """Atomically claim one pending job (caller must use BEGIN IMMEDIATE).

    Returns job dict or None if no jobs available.
    Pattern: SELECT id → UPDATE WHERE id AND status='pending' → check rowcount.
    """
    row = conn.execute(
        """SELECT id FROM health_jobs
           WHERE status = 'pending' AND scheduled_at <= datetime('now')
           ORDER BY scheduled_at ASC LIMIT 1"""
    ).fetchone()
    if row is None:
        return None

    job_id = row["id"]
    cursor = conn.execute(
        """UPDATE health_jobs
           SET status = 'running', claimed_at = ?, worker_id = ?
           WHERE id = ? AND status = 'pending'""",
        (_now(), worker_id, job_id),
    )
    if cursor.rowcount == 0:
        return None  # Another worker claimed it first

    return dict(conn.execute(
        "SELECT * FROM health_jobs WHERE id = ?", (job_id,)
    ).fetchone())


def complete_job(conn, job_id: int, success: bool = True) -> bool:
    """Mark a job as done or failed."""
    status = "done" if success else "failed"
    cursor = conn.execute(
        "UPDATE health_jobs SET status = ?, completed_at = ? WHERE id = ? AND status = 'running'",
        (status, _now(), job_id),
    )
    return cursor.rowcount > 0


def enqueue_pending_services(conn) -> int:
    """Enqueue health jobs for services that have no pending/running job.

    Must be called inside a BEGIN IMMEDIATE transaction to prevent duplicates.
    Computes scheduled_at inside the transaction (not before).
    """
    cursor = conn.execute(
        """INSERT INTO health_jobs (service_id, status, scheduled_at)
           SELECT id, 'pending', datetime('now')
           FROM services
           WHERE id NOT IN (
               SELECT service_id FROM health_jobs
               WHERE status IN ('pending', 'running')
           )"""
    )
    return cursor.rowcount
