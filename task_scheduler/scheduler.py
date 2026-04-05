"""
Distributed task scheduler process.

Polls the `schedules` table every POLL_INTERVAL seconds. For each schedule
that is due (next_run_at <= now AND status='active'), atomically advances
next_run_at and inserts a job_run into the queue.

Atomic claim pattern (from job-queue solution doc):
  1. SELECT id of due schedule
  2. BEGIN IMMEDIATE (exclusive write lock)
  3. Compute new_next_run_at from now (skip, not back-fill)
  4. UPDATE schedules SET next_run_at=<next> WHERE id=? AND next_run_at=<old_value>
  5. Check rowcount — if 0, another process beat us; ROLLBACK and skip
  6. INSERT job_run
  7. COMMIT

Steps 3-7 run inside BEGIN IMMEDIATE to prevent the crash window where
next_run_at is advanced but the job_run insert hasn't happened yet.

Usage:
    python scheduler.py
    POLL_INTERVAL=5 python scheduler.py   # faster polling (seconds)
"""
import os
import signal
import sqlite3
import time
import logging
from datetime import datetime, timezone
from croniter import croniter, CroniterBadCronError

from db import get_connection

# Guard against zero/negative interval causing CPU busy-poll
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

    # Guard against connection assignment failure
    conn = None
    try:
        conn = get_connection()

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

            # Validate cron before acquiring the write lock — a bad cron on one
            # schedule must not abort all remaining candidates in this poll cycle.
            try:
                # Advance to the next fire AFTER now (skip, not back-fill).
                # Computing inside the transaction boundary ensures the value
                # is fresh and not from a stale clock snapshot taken earlier.
                new_next_run_at = _next_run_at(cron_expr, now)
            except (CroniterBadCronError, ValueError):
                log.error(
                    "Schedule %d has invalid cron_expr %r — skipping",
                    schedule_id, cron_expr,
                )
                continue

            # BEGIN IMMEDIATE: exclusive write lock for the claim + insert pair.
            try:
                conn.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as e:
                log.warning(
                    "DB locked for schedule %d, will retry next poll: %s",
                    schedule_id, e,
                )
                continue

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
                    log.debug("Schedule %d already claimed — skipping", schedule_id)
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
                log.error("Failed to claim schedule %d", schedule_id, exc_info=True)
                # continue processing remaining candidates

    finally:
        if conn:
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
