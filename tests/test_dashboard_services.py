"""Tests for service registry DB layer."""
import pytest

from dashboard.db import get_db, init_db
from dashboard.services import (
    create_service, delete_service, get_dashboard, get_service, list_services
)
from dashboard.health import record_result


@pytest.fixture
def conn(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    with get_db(path=db_path) as c:
        yield c


def test_create_service(conn):
    s = create_service(conn, "my-api", "http://example.com/health")
    assert s["name"] == "my-api"
    assert s["health_check_url"] == "http://example.com/health"
    assert "id" in s


def test_create_service_duplicate_name_raises(conn):
    import sqlite3
    create_service(conn, "dup", "http://example.com/health")
    with pytest.raises(sqlite3.IntegrityError):
        create_service(conn, "dup", "http://example.com/health2")


def test_get_service(conn):
    s = create_service(conn, "svc", "http://example.com/health")
    got = get_service(conn, s["id"])
    assert got["id"] == s["id"]


def test_get_service_not_found(conn):
    assert get_service(conn, "nonexistent") is None


def test_list_services(conn):
    create_service(conn, "b-svc", "http://b.example.com/health")
    create_service(conn, "a-svc", "http://a.example.com/health")
    svcs = list_services(conn)
    assert len(svcs) == 2
    assert svcs[0]["name"] == "a-svc"  # sorted by name


def test_delete_service(conn):
    s = create_service(conn, "del-me", "http://example.com/health")
    assert delete_service(conn, s["id"]) is True
    assert get_service(conn, s["id"]) is None


def test_delete_service_not_found(conn):
    assert delete_service(conn, "ghost") is False


def test_get_dashboard_no_health(conn):
    create_service(conn, "unchecked", "http://example.com/health")
    dashboard = get_dashboard(conn)
    assert len(dashboard) == 1
    assert dashboard[0]["health_status"] is None


def test_get_dashboard_with_health(conn):
    s = create_service(conn, "checked", "http://example.com/health")
    record_result(conn, s["id"], "healthy", status_code=200, response_time_ms=50)
    dashboard = get_dashboard(conn)
    assert dashboard[0]["health_status"] == "healthy"
    assert dashboard[0]["last_status_code"] == 200
