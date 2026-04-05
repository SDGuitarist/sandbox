"""
Distributed task scheduler process.

Polls the `schedules` table every POLL_INTERVAL seconds. For each schedule
that is due (next_run_at <= now AND status='active'), atomically advances
next_run_at and inserts a job_run into the queue.

Atomic claim pattern (from job-queue solution doc):
  1. SELECT id of due schedule
  2. UPDATE schedules SET next_run_at=<next> WHERE id=? AND next_run_at=<old_value>
  3. Check rowcount — if 0, another process beat us; skip this schedule
  4. Only if rowcount=1: INSERT the job_run

Both steps 2 and 3 run inside BEGIN IMMEDIATE to prevent the crash window
where next_run_at is advanced but the job_run insert hasn't happened yet.

Usage:
    python scheduler.py
    POLL_INTERVAL=5 python scheduler.py   # faster polling (seconds)
"""
import os
import signal
import time
import logging
from datetime import datetime, timezone
from croniter import croniter

from db import get_connection

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "10"))

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


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _next_run_at(cron_expr: str, after: str) -> str:
    """Compute next ISO datetime string after `after` for `cron_expr`."""
    base = datetime.strptime(after, "%Y-%m-%d %H:%M:%S")
    cron = croniter(cron_expr, base)
    return cron.get_next(datetime).strftime("%Y-%m-%d %H:%M:%S")


def _fire_due_schedules():
    """Find all due schedules and atomically spawn job_runs for them."""
    now = _now_str()

    conn = get_connection()
    try:
        # Find candidates — may include false positives if another process
        # already claimed them; the UPDATE below is the real gate.
        candidates = conn.execute(
            """
            SELECT id, cron_expr, payload, next_run_at
            FROM schedules
            WHERE status = 'active' AND next_run_at <= ?
            """,
            (now,),
        ).fetchall()

        for row in candidates:
            schedule_id = row["id"]
            cron_expr = row["cron_expr"]
            payload = row["payload"]
            old_next_run_at = row["next_run_at"]

            # Advance to the next fire AFTER now (skip, not back-fill).
            # If old_next_run_at is multiple periods in the past, we jump
            # straight to the next occurrence after the current time so the
            # schedule doesn't immediately re-fire on the next poll.
            new_next_run_at = _next_run_at(cron_expr, now)

            # BEGIN IMMEDIATE: exclusive write lock for the claim + insert pair.
            # This ensures no crash window between advancing next_run_at and
            # inserting the job_run.
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.execute(
                    """
                    UPDATE schedules
                    SET next_run_at = ?
                    WHERE id = ? AND next_run_at = ? AND status = 'active'
                    """,
                    (new_next_run_at, schedule_id, old_next_run_at),
                )
                if cur.rowcount == 0:
                    # Another scheduler process already claimed this schedule
                    conn.execute("ROLLBACK")
                    log.debug("Schedule %d already claimed by another process — skipping", schedule_id)
                    continue

                conn.execute(
                    """
                    INSERT INTO job_runs (schedule_id, payload, status)
                    VALUES (?, ?, 'pending')
                    """,
                    (schedule_id, payload),
                )
                conn.execute("COMMIT")
                log.info(
                    "Spawned job_run for schedule %d (cron=%r), next_run_at=%s",
                    schedule_id, cron_expr, new_next_run_at,
                )
            except Exception:
                conn.execute("ROLLBACK")
                raise

    finally:
        conn.close()


def run():
    """Main scheduler loop."""
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    log.info("Scheduler started (poll_interval=%ds)", POLL_INTERVAL)

    while _running:
        try:
            _fire_due_schedules()
        except Exception as exc:
            log.error("Error during poll: %s", exc, exc_info=True)

        # Sleep in small increments so SIGINT is responsive
        for _ in range(POLL_INTERVAL * 10):
            if not _running:
                break
            time.sleep(0.1)

    log.info("Scheduler stopped")


if __name__ == "__main__":
    run()
