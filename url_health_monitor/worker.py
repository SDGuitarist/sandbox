"""
Health check worker process.

Polls check_jobs every POLL_INTERVAL seconds. For each pending job:
1. Atomically claims it (UPDATE WHERE id=? AND status='pending', check rowcount)
2. Fetches the monitored URL config
3. Performs requests.get(url, timeout=timeout_seconds)
4. Records result in check_results
5. Updates check_jobs status → completed/failed
6. Updates monitored_urls.current_status based on last failure_threshold results

Status update logic (see plan for full rationale):
  - Query last failure_threshold results by checked_at DESC
  - If fewer than failure_threshold results exist → 'unknown'
  - If ALL are failures (error_message IS NOT NULL) → 'degraded'
  - If ANY succeeded (error_message IS NULL) → 'healthy'
  - Also updates last_checked_at

Timeout recovery: reset running→pending for jobs claimed > 120s ago.

Usage:
    python worker.py
    WORKER_ID=worker-1 POLL_INTERVAL=2 python worker.py
"""
import os
import signal
import sqlite3
import time
import logging
import uuid
from datetime import datetime, timezone

import requests
from requests.exceptions import RequestException, Timeout, SSLError

from db import get_connection

POLL_INTERVAL = max(1, int(os.environ.get("POLL_INTERVAL", "2")))
WORKER_ID = os.environ.get("WORKER_ID") or str(uuid.uuid4())
JOB_TIMEOUT_SECONDS = 120  # reset running→pending after this many seconds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker:" + WORKER_ID[:8] + "] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

_running = True


def _handle_shutdown(signum, frame):
    global _running
    log.info("Shutdown signal received — stopping after current poll")
    _running = False


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _update_url_status(conn, url_id: int, failure_threshold: int):
    """
    Recompute and persist current_status for url_id based on the last
    failure_threshold check_results rows, ordered newest-first.

    Rules:
      - fewer than failure_threshold results → 'unknown'
      - ALL have error_message IS NOT NULL → 'degraded'
      - ANY has error_message IS NULL → 'healthy'
    """
    results = conn.execute(
        """
        SELECT error_message FROM check_results
        WHERE url_id = ?
        ORDER BY checked_at DESC
        LIMIT ?
        """,
        (url_id, failure_threshold),
    ).fetchall()

    if len(results) < failure_threshold:
        new_status = "unknown"
    elif all(r["error_message"] is not None for r in results):
        new_status = "degraded"
    else:
        new_status = "healthy"

    conn.execute(
        "UPDATE monitored_urls SET current_status = ?, last_checked_at = ? WHERE id = ?",
        (new_status, _now_str(), url_id),
    )
    return new_status


def _recover_stale_jobs(conn):
    """Reset running→pending for jobs claimed too long ago."""
    conn.execute(
        """
        UPDATE check_jobs
        SET status = 'pending', claimed_at = NULL, worker_id = NULL
        WHERE status = 'running'
          AND claimed_at <= datetime('now', ? || ' seconds')
        """,
        (f"-{JOB_TIMEOUT_SECONDS}",),
    )
    conn.commit()


def _process_one_job() -> bool:
    """
    Claim and process one pending job. Returns True if a job was processed,
    False if no pending jobs exist.
    """
    conn = None
    try:
        conn = get_connection()

        # Recover stale jobs first
        _recover_stale_jobs(conn)

        # Find one pending job
        row = conn.execute(
            """
            SELECT id FROM check_jobs
            WHERE status = 'pending'
            ORDER BY created_at ASC LIMIT 1
            """
        ).fetchone()

        if row is None:
            return False

        job_id = row["id"]
        now = _now_str()

        # Atomic claim
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as e:
            log.warning("DB locked during claim: %s", e)
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            return False

        try:
            cur = conn.execute(
                """
                UPDATE check_jobs
                SET status = 'running', claimed_at = ?, worker_id = ?
                WHERE id = ? AND status = 'pending'
                """,
                (now, WORKER_ID, job_id),
            )
            if cur.rowcount == 0:
                conn.execute("ROLLBACK")
                return False
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise

        # Fetch URL config for this job
        url_row = conn.execute(
            """
            SELECT u.id, u.url, u.timeout_seconds, u.failure_threshold
            FROM check_jobs j
            JOIN monitored_urls u ON u.id = j.url_id
            WHERE j.id = ?
            """,
            (job_id,),
        ).fetchone()

        if url_row is None:
            # Orphaned job — mark failed
            conn.execute(
                "UPDATE check_jobs SET status='failed', completed_at=? WHERE id=?",
                (_now_str(), job_id),
            )
            conn.commit()
            return True

        url = url_row["url"]
        timeout_seconds = url_row["timeout_seconds"]
        failure_threshold = url_row["failure_threshold"]
        url_id = url_row["id"]

        # Perform HTTP check
        http_status_code = None
        response_time_ms = None
        error_message = None

        start_ms = int(time.time() * 1000)
        try:
            resp = requests.get(url, timeout=timeout_seconds, allow_redirects=True)
            response_time_ms = int(time.time() * 1000) - start_ms
            http_status_code = resp.status_code
            # Treat non-2xx as an error for health monitoring purposes
            if not resp.ok:
                error_message = f"HTTP {resp.status_code}"
            log.info("Checked %s → %d in %dms", url, http_status_code, response_time_ms)
        except Timeout:
            response_time_ms = int(time.time() * 1000) - start_ms
            error_message = f"Timeout after {timeout_seconds}s"
            log.warning("Timeout checking %s", url)
        except SSLError as e:
            error_message = f"SSL error: {e}"
            log.warning("SSL error checking %s: %s", url, e)
        except RequestException as e:
            error_message = f"Request error: {e}"
            log.warning("Request error checking %s: %s", url, e)

        checked_at = _now_str()
        job_status = "failed" if error_message else "completed"

        # Record result + update job + update URL status (single transaction)
        conn.execute(
            """
            INSERT INTO check_results
                (job_id, url_id, http_status_code, response_time_ms, error_message, checked_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, url_id, http_status_code, response_time_ms, error_message, checked_at),
        )
        conn.execute(
            "UPDATE check_jobs SET status=?, completed_at=? WHERE id=?",
            (job_status, checked_at, job_id),
        )
        new_status = _update_url_status(conn, url_id, failure_threshold)
        conn.commit()

        log.info(
            "url_id=%d status→%s (error=%s)",
            url_id, new_status, error_message or "none",
        )
        return True

    finally:
        if conn:
            conn.close()


def run():
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    log.info("Worker started (id=%s, poll_interval=%ds)", WORKER_ID, POLL_INTERVAL)

    while _running:
        try:
            processed = _process_one_job()
            if not processed:
                # No jobs — wait before polling again
                for _ in range(POLL_INTERVAL * 10):
                    if not _running:
                        break
                    time.sleep(0.1)
        except Exception as exc:
            log.error("Unhandled error: %s", exc, exc_info=True)
            time.sleep(1)

    log.info("Worker stopped")


if __name__ == "__main__":
    run()
