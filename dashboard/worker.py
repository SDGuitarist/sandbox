"""Health check worker — runs as a separate process.

Usage:
    python -m dashboard.worker [--db PATH] [--interval SECONDS]

Polls health_jobs for pending jobs, claims atomically, performs HTTP GET,
records result, appends event on status change, marks job done/failed.
"""
import os
import sys
import time
import uuid
import argparse

import requests

from .db import DB_PATH, get_db, init_db
from .health import get_latest_status, record_result
from .jobs import claim_job, complete_job
from .events import append_event
from .services import get_service


def check_service_url(url: str, timeout: int = 5) -> dict:
    """Perform HTTP GET to the health check URL.

    Returns dict with status, status_code, response_time_ms, error_message.
    Never follows redirects (SSRF layer 2).
    """
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=False)
        response_time_ms = int(resp.elapsed.total_seconds() * 1000)
        if resp.status_code < 300:
            return {
                "status": "healthy",
                "status_code": resp.status_code,
                "response_time_ms": response_time_ms,
                "error_message": None,
            }
        else:
            # 3xx treated as degraded — with allow_redirects=False, a redirect
            # means the service is not responding normally at its registered URL.
            return {
                "status": "degraded",
                "status_code": resp.status_code,
                "response_time_ms": response_time_ms,
                "error_message": f"HTTP {resp.status_code}",
            }
    except requests.exceptions.Timeout:
        return {
            "status": "degraded",
            "status_code": None,
            "response_time_ms": None,
            "error_message": "Request timed out",
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "unknown",
            "status_code": None,
            "response_time_ms": None,
            "error_message": f"{type(e).__name__}: {str(e)[:200]}",
        }


def process_one_job(db_path: str, worker_id: str) -> bool:
    """Claim and process one pending job. Returns True if a job was processed."""
    with get_db(path=db_path, immediate=True) as conn:
        job = claim_job(conn, worker_id)

    if job is None:
        return False

    with get_db(path=db_path) as conn:
        service = get_service(conn, job["service_id"])

    if service is None:
        with get_db(path=db_path, immediate=True) as conn:
            complete_job(conn, job["id"], success=False)
        return True

    check_result = check_service_url(service["health_check_url"])

    with get_db(path=db_path, immediate=True) as conn:
        # Get previous status before recording new one
        previous = get_latest_status(conn, service["id"])
        prev_status = previous["status"] if previous else None

        record_result(
            conn,
            service_id=service["id"],
            status=check_result["status"],
            status_code=check_result["status_code"],
            response_time_ms=check_result["response_time_ms"],
            error_message=check_result["error_message"],
        )
        complete_job(conn, job["id"], success=True)

        # Append event only if status changed
        if check_result["status"] != prev_status:
            append_event(
                conn,
                event_type="health.changed",
                service_id=service["id"],
                payload={
                    "from": prev_status,
                    "to": check_result["status"],
                    "service_name": service["name"],
                },
            )

    return True


def run_worker(db_path: str, poll_interval: float = 2.0):
    """Main worker loop. Runs until interrupted."""
    init_db(db_path)
    worker_id = f"worker:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    print(f"Worker {worker_id} started, polling every {poll_interval}s")

    try:
        while True:
            processed = process_one_job(db_path, worker_id)
            if not processed:
                time.sleep(poll_interval)
    except KeyboardInterrupt:
        print(f"Worker {worker_id} stopped")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Dashboard health check worker")
    parser.add_argument("--db", default=os.environ.get("DASHBOARD_DB", DB_PATH))
    parser.add_argument("--interval", type=float, default=2.0, metavar="SECONDS")
    args = parser.parse_args()
    run_worker(args.db, args.interval)


if __name__ == "__main__":
    main()
