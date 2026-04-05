"""Tests for health results and job queue."""
import pytest

from dashboard.db import get_db, init_db
from dashboard.health import get_latest_status, list_results, record_result
from dashboard.jobs import claim_job, complete_job, enqueue_job, enqueue_pending_services
from dashboard.services import create_service


@pytest.fixture
def env(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


def test_record_result(env):
    with get_db(path=env) as conn:
        s = create_service(conn, "svc", "http://example.com/health")
        r = record_result(conn, s["id"], "healthy", status_code=200, response_time_ms=42)
    assert r["status"] == "healthy"
    assert r["status_code"] == 200


def test_get_latest_status(env):
    with get_db(path=env) as conn:
        s = create_service(conn, "svc", "http://example.com/health")
        record_result(conn, s["id"], "healthy", status_code=200)
        record_result(conn, s["id"], "degraded", status_code=500)
        latest = get_latest_status(conn, s["id"])
    assert latest["status"] == "degraded"


def test_get_latest_status_none(env):
    with get_db(path=env) as conn:
        s = create_service(conn, "svc", "http://example.com/health")
        assert get_latest_status(conn, s["id"]) is None


def test_list_results(env):
    with get_db(path=env) as conn:
        s = create_service(conn, "svc", "http://example.com/health")
        for i in range(3):
            record_result(conn, s["id"], "healthy", status_code=200)
        results = list_results(conn, s["id"])
    assert len(results) == 3


def test_enqueue_job(env):
    with get_db(path=env) as conn:
        s = create_service(conn, "svc", "http://example.com/health")
        job = enqueue_job(conn, s["id"])
    assert job["status"] == "pending"
    assert job["service_id"] == s["id"]


def test_claim_job_atomic(env):
    with get_db(path=env) as conn:
        s = create_service(conn, "svc", "http://example.com/health")
        enqueue_job(conn, s["id"])

    with get_db(path=env, immediate=True) as conn:
        job = claim_job(conn, "worker-1")
    assert job is not None
    assert job["status"] == "running"
    assert job["worker_id"] == "worker-1"

    # Second claim should return None
    with get_db(path=env, immediate=True) as conn:
        job2 = claim_job(conn, "worker-2")
    assert job2 is None


def test_complete_job(env):
    with get_db(path=env) as conn:
        s = create_service(conn, "svc", "http://example.com/health")
        job = enqueue_job(conn, s["id"])

    with get_db(path=env, immediate=True) as conn:
        claimed = claim_job(conn, "w1")

    with get_db(path=env, immediate=True) as conn:
        complete_job(conn, claimed["id"], success=True)

    with get_db(path=env) as conn:
        row = conn.execute("SELECT status FROM health_jobs WHERE id = ?", (claimed["id"],)).fetchone()
    assert row["status"] == "done"


def test_complete_job_status_guard(env):
    """complete_job must not double-complete — requires status='running' guard."""
    with get_db(path=env) as conn:
        s = create_service(conn, "svc", "http://example.com/health")
        job = enqueue_job(conn, s["id"])

    with get_db(path=env, immediate=True) as conn:
        claimed = claim_job(conn, "w1")

    with get_db(path=env, immediate=True) as conn:
        result1 = complete_job(conn, claimed["id"], success=True)
    assert result1 is True

    # Second call — job is now 'done', not 'running' — must return False
    with get_db(path=env, immediate=True) as conn:
        result2 = complete_job(conn, claimed["id"], success=True)
    assert result2 is False


def test_enqueue_pending_services(env):
    with get_db(path=env) as conn:
        create_service(conn, "s1", "http://a.example.com/health")
        create_service(conn, "s2", "http://b.example.com/health")

    with get_db(path=env, immediate=True) as conn:
        count = enqueue_pending_services(conn)
    assert count == 2

    # Second enqueue: no new jobs for services already queued
    with get_db(path=env, immediate=True) as conn:
        count2 = enqueue_pending_services(conn)
    assert count2 == 0
