"""Health check scheduler — runs as a separate process.

Usage:
    python -m dashboard.scheduler [--db PATH] [--interval SECONDS]

Enqueues health_jobs for services that have no pending/running job.
"""
import argparse
import os
import sys
import time

from .db import DB_PATH, get_db, init_db
from .jobs import enqueue_pending_services


def run_scheduler(db_path: str, interval: float = 30.0):
    """Main scheduler loop. Enqueues jobs, sleeps, repeat."""
    init_db(db_path)
    print(f"Scheduler started, enqueuing every {interval}s")
    try:
        while True:
            with get_db(path=db_path, immediate=True) as conn:
                count = enqueue_pending_services(conn)
            if count:
                print(f"Enqueued {count} health check job(s)")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Scheduler stopped")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Dashboard health check scheduler")
    parser.add_argument("--db", default=os.environ.get("DASHBOARD_DB", DB_PATH))
    parser.add_argument("--interval", type=float, default=30.0, metavar="SECONDS")
    args = parser.parse_args()
    run_scheduler(args.db, args.interval)


if __name__ == "__main__":
    main()
