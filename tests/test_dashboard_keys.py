"""Tests for API key management."""
import pytest

from dashboard.db import get_db, init_db
from dashboard.keys import create_key, list_keys, revoke_key, validate_key


@pytest.fixture
def conn(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    with get_db(path=db_path) as c:
        yield c


def test_create_key_returns_raw_key(conn):
    result = create_key(conn, label="test-key")
    assert "key" in result
    assert len(result["key"]) == 64  # token_hex(32)
    assert result["prefix"] == result["key"][:8]


def test_validate_key_success(conn):
    k = create_key(conn, label="valid")
    info = validate_key(conn, k["key"])
    assert info is not None
    assert info["label"] == "valid"


def test_validate_key_wrong_key(conn):
    create_key(conn, label="valid")
    assert validate_key(conn, "a" * 64) is None


def test_validate_key_revoked(conn):
    k = create_key(conn, label="rev")
    revoke_key(conn, k["id"])
    assert validate_key(conn, k["key"]) is None


def test_validate_key_too_short(conn):
    assert validate_key(conn, "short") is None


def test_revoke_key(conn):
    k = create_key(conn, label="rev")
    assert revoke_key(conn, k["id"]) is True


def test_revoke_nonexistent_key(conn):
    assert revoke_key(conn, "ghost") is False


def test_list_keys_no_key_material(conn):
    create_key(conn, label="k1")
    keys = list_keys(conn)
    assert len(keys) == 1
    assert "key" not in keys[0]
    assert "key_hash" not in keys[0]
    assert "salt" not in keys[0]


def test_list_keys_by_service(conn):
    from dashboard.services import create_service
    s = create_service(conn, "svc", "http://example.com/health")
    k1 = create_key(conn, label="svc-key", service_id=s["id"])
    k2 = create_key(conn, label="global-key")
    svc_keys = list_keys(conn, service_id=s["id"])
    assert len(svc_keys) == 1
    assert svc_keys[0]["id"] == k1["id"]
