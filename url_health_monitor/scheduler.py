"""
Health check scheduler process.

Polls the monitored_urls table every POLL_INTERVAL seconds. For each active
URL whose last check was more than check_interval_seconds ago (or never
checked), enqueues a new check_job — but only if no pending/running job
already exists for that URL (prevents pile-up during slow checks).

Usage:
    python scheduler.py
    POLL_INTERVAL=5 python scheduler.py
"""
import os
import signal
import sqlite3
import time
import logging

from db import get_connection

POLL_INTERVAL = max(1, int(os.environ.get("POLL_INTERVAL", "10")))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [scheduler] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

_running = True


def _handle_shutdown(signum, frame):
    global _running
    log.info("Shutdown signal received — stopping after current poll")
    _running = False


def _enqueue_due_urls():
    """Find URLs due for a health check and enqueue check_jobs for them."""
    conn = None
    try:
        conn = get_connection()

        # URLs that are due: never checked OR last_checked_at is old enough
        due_urls = conn.execute(
            """
            SELECT u.id, u.check_interval_seconds
            FROM monitored_urls u
            WHERE u.current_status != 'deleted'
              AND (
                  u.last_checked_at IS NULL
                  OR u.last_checked_at <= datetime('now', '-' || u.check_interval_seconds || ' seconds')
              )
              AND NOT EXISTS (
                  SELECT 1 FROM check_jobs j
                  WHERE j.url_id = u.id AND j.status IN ('pending', 'running')
              )
            """
        ).fetchall()

        for row in due_urls:
            url_id = row["id"]
            try:
                conn.execute("BEGIN IMMEDIATE")
                # Re-check the NOT EXISTS guard INSIDE the lock to prevent duplicate
                # jobs when multiple scheduler processes race on the same URL.
                cur = conn.execute(
                    """
                    INSERT INTO check_jobs (url_id, status)
                    SELECT ?, 'pending'
                    WHERE NOT EXISTS (
                        SELECT 1 FROM check_jobs
                        WHERE url_id = ? AND status IN ('pending', 'running')
                    )
                    """,
                    (url_id, url_id),
                )
                conn.execute("COMMIT")
                if cur.rowcount:
                    log.info("Enqueued check_job for url_id=%d", url_id)
                else:
                    log.debug("Skipped url_id=%d — job already pending/running", url_id)
            except sqlite3.OperationalError as e:
                log.warning("DB locked for url_id=%d, will retry: %s", url_id, e)
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                continue
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                log.error("Failed to enqueue url_id=%d", url_id, exc_info=True)
    finally:
        if conn:
            conn.close()


def run():
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    log.info("Scheduler started (poll_interval=%ds)", POLL_INTERVAL)

    while _running:
        try:
            _enqueue_due_urls()
        except Exception as exc:
            log.error("Error during poll: %s", exc, exc_info=True)

        for _ in range(POLL_INTERVAL * 10):
            if not _running:
                break
            time.sleep(0.1)

    log.info("Scheduler stopped")


if __name__ == "__main__":
    run()
