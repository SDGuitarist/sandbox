"""DB layer tests: CRUD, evaluation, determinism."""
import pytest

from flags.db import (
    add_dependency, create_flag, delete_flag, evaluate_flag,
    get_dependencies, get_flag, init_db, list_flags, update_flag,
    _hash_bucket,
)


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path=path)
    return path


# ── CRUD ──────────────────────────────────────────────────────────────────────

def test_create_flag(db):
    flag = create_flag("dark_mode", "Dark Mode", db_path=db)
    assert flag["key"] == "dark_mode"
    assert flag["enabled"] is True
    assert flag["default_enabled"] is False
    assert flag["eval_count"] == 0
    assert "T" not in flag["created_at"]


def test_create_flag_duplicate_raises(db):
    import sqlite3
    create_flag("flag_a", "A", db_path=db)
    with pytest.raises(sqlite3.IntegrityError):
        create_flag("flag_a", "A duplicate", db_path=db)


def test_get_flag_not_found(db):
    assert get_flag("nonexistent", db_path=db) is None


def test_list_flags(db):
    create_flag("a", "A", db_path=db)
    create_flag("b", "B", db_path=db)
    flags = list_flags(db_path=db)
    assert len(flags) == 2
    assert flags[0]["key"] == "a"


def test_update_flag_partial(db):
    create_flag("flag", "Original", db_path=db)
    updated = update_flag("flag", {"name": "Updated", "enabled": False}, db_path=db)
    assert updated["name"] == "Updated"
    assert updated["enabled"] is False


def test_update_flag_not_found(db):
    assert update_flag("missing", {"name": "x"}, db_path=db) is None


def test_update_flag_ignores_disallowed_columns(db):
    create_flag("flag", "Original", db_path=db)
    # eval_count is not patchable
    result = update_flag("flag", {"eval_count": 9999, "name": "Safe"}, db_path=db)
    assert result["eval_count"] == 0  # unchanged
    assert result["name"] == "Safe"


def test_delete_flag(db):
    create_flag("flag", "To delete", db_path=db)
    assert delete_flag("flag", db_path=db) is True
    assert get_flag("flag", db_path=db) is None


def test_delete_flag_not_found(db):
    assert delete_flag("missing", db_path=db) is False


# ── Evaluation ────────────────────────────────────────────────────────────────

def test_evaluate_disabled_flag(db):
    create_flag("flag", "F", enabled=False, db_path=db)
    result = evaluate_flag("flag", "user1", db_path=db)
    assert result["enabled"] is False
    assert result["reason"] == "disabled"


def test_evaluate_environment_mismatch(db):
    create_flag("flag", "F", environments=["production"], db_path=db)
    result = evaluate_flag("flag", "user1", environment="staging", db_path=db)
    assert result["enabled"] is False
    assert result["reason"] == "environment_mismatch"


def test_evaluate_environment_match(db):
    create_flag("flag", "F", environments=["production"], default_enabled=True, db_path=db)
    result = evaluate_flag("flag", "user1", environment="production", db_path=db)
    assert result["reason"] != "environment_mismatch"


def test_evaluate_allowlist_hit(db):
    create_flag("flag", "F", allowlist=["alice", "bob"], db_path=db)
    result = evaluate_flag("flag", "alice", db_path=db)
    assert result["enabled"] is True
    assert result["reason"] == "allowlist"


def test_evaluate_allowlist_miss(db):
    create_flag("flag", "F", allowlist=["alice"], default_enabled=False, db_path=db)
    result = evaluate_flag("flag", "charlie", db_path=db)
    assert result["reason"] != "allowlist"


def test_evaluate_percentage_100(db):
    create_flag("flag", "F", percentage=100, db_path=db)
    result = evaluate_flag("flag", "any_user", db_path=db)
    assert result["enabled"] is True
    assert result["reason"] == "percentage"


def test_evaluate_percentage_0(db):
    create_flag("flag", "F", percentage=0, db_path=db)
    result = evaluate_flag("flag", "any_user", db_path=db)
    assert result["enabled"] is False
    assert result["reason"] == "percentage"


def test_evaluate_default_true(db):
    create_flag("flag", "F", default_enabled=True, db_path=db)
    result = evaluate_flag("flag", "user1", db_path=db)
    assert result["enabled"] is True
    assert result["reason"] == "default"


def test_evaluate_default_false(db):
    create_flag("flag", "F", default_enabled=False, db_path=db)
    result = evaluate_flag("flag", "user1", db_path=db)
    assert result["enabled"] is False
    assert result["reason"] == "default"


def test_evaluate_increments_eval_count(db):
    create_flag("flag", "F", db_path=db)
    for _ in range(3):
        evaluate_flag("flag", "user1", db_path=db)
    flag = get_flag("flag", db_path=db)
    assert flag["eval_count"] == 3


def test_evaluate_determinism(db):
    """Same user always gets same result for a given flag."""
    create_flag("flag", "F", percentage=50, db_path=db)
    results = [evaluate_flag("flag", "alice", db_path=db)["enabled"] for _ in range(5)]
    assert len(set(results)) == 1  # all same


def test_evaluate_not_found(db):
    result = evaluate_flag("nonexistent", "user1", db_path=db)
    assert result["enabled"] is False
    assert result["reason"] == "not_found"


def test_evaluate_dependency_disabled(db):
    create_flag("gate", "Gate", enabled=False, db_path=db)
    create_flag("feature", "Feature", default_enabled=True, db_path=db)
    add_dependency("feature", "gate", db_path=db)
    result = evaluate_flag("feature", "user1", db_path=db)
    assert result["enabled"] is False
    assert result["reason"] == "dependency_disabled"
    assert result["dependency"] == "gate"


def test_evaluate_dependency_enabled(db):
    create_flag("gate", "Gate", default_enabled=True, db_path=db)
    create_flag("feature", "Feature", default_enabled=True, db_path=db)
    add_dependency("feature", "gate", db_path=db)
    result = evaluate_flag("feature", "user1", db_path=db)
    assert result["enabled"] is True


def test_hash_bucket_is_deterministic():
    b1 = _hash_bucket("dark_mode", "alice")
    b2 = _hash_bucket("dark_mode", "alice")
    assert b1 == b2
    assert 0 <= b1 <= 99


def test_hash_bucket_different_users_differ():
    buckets = {_hash_bucket("flag", f"user_{i}") for i in range(100)}
    assert len(buckets) > 10  # confirms reasonable distribution
