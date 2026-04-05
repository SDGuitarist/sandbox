"""Integration tests for all feature flag API routes."""
import pytest

from flags.app import create_app
from flags.db import add_dependency, create_flag


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, db_path


# ── POST /flags ───────────────────────────────────────────────────────────────

def test_create_flag_201(client):
    c, _ = client
    resp = c.post("/flags", json={"key": "dark_mode", "name": "Dark Mode"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["key"] == "dark_mode"
    assert data["enabled"] is True
    assert data["eval_count"] == 0


def test_create_flag_missing_key_400(client):
    c, _ = client
    resp = c.post("/flags", json={"name": "No Key"})
    assert resp.status_code == 400


def test_create_flag_missing_name_400(client):
    c, _ = client
    resp = c.post("/flags", json={"key": "flag"})
    assert resp.status_code == 400


def test_create_flag_duplicate_409(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "Flag"})
    resp = c.post("/flags", json={"key": "flag", "name": "Flag"})
    assert resp.status_code == 409


def test_create_flag_invalid_percentage_400(client):
    c, _ = client
    resp = c.post("/flags", json={"key": "f", "name": "F", "percentage": 150})
    assert resp.status_code == 400


def test_create_flag_invalid_environments_400(client):
    c, _ = client
    resp = c.post("/flags", json={"key": "f", "name": "F", "environments": "production"})
    assert resp.status_code == 400


def test_create_flag_with_all_fields(client):
    c, _ = client
    resp = c.post("/flags", json={
        "key": "beta",
        "name": "Beta Feature",
        "environments": ["production"],
        "allowlist": ["alice"],
        "percentage": 50,
        "default_enabled": False,
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["environments"] == ["production"]
    assert data["allowlist"] == ["alice"]
    assert data["percentage"] == 50


# ── GET /flags ────────────────────────────────────────────────────────────────

def test_list_flags(client):
    c, _ = client
    c.post("/flags", json={"key": "a", "name": "A"})
    c.post("/flags", json={"key": "b", "name": "B"})
    resp = c.get("/flags")
    assert resp.status_code == 200
    assert len(resp.get_json()["flags"]) == 2


# ── GET /flags/<key> ──────────────────────────────────────────────────────────

def test_get_flag_200(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "Flag"})
    resp = c.get("/flags/flag")
    assert resp.status_code == 200
    assert resp.get_json()["key"] == "flag"
    assert "dependencies" in resp.get_json()


def test_get_flag_404(client):
    c, _ = client
    assert c.get("/flags/nonexistent").status_code == 404


# ── PATCH /flags/<key> ────────────────────────────────────────────────────────

def test_patch_flag_200(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "Original"})
    resp = c.patch("/flags/flag", json={"name": "Updated", "enabled": False})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "Updated"
    assert data["enabled"] is False


def test_patch_flag_404(client):
    c, _ = client
    assert c.patch("/flags/missing", json={"name": "x"}).status_code == 404


def test_patch_flag_eval_count_ignored(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "F"})
    resp = c.patch("/flags/flag", json={"eval_count": 9999})
    assert resp.get_json()["eval_count"] == 0


# ── DELETE /flags/<key> ───────────────────────────────────────────────────────

def test_delete_flag_204(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "F"})
    resp = c.delete("/flags/flag")
    assert resp.status_code == 204
    assert c.get("/flags/flag").status_code == 404


def test_delete_flag_404(client):
    c, _ = client
    assert c.delete("/flags/nonexistent").status_code == 404


# ── POST /flags/<key>/evaluate ────────────────────────────────────────────────

def test_evaluate_disabled_returns_false(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "F", "enabled": False})
    resp = c.post("/flags/flag/evaluate", json={"user_id": "alice"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["enabled"] is False
    assert data["reason"] == "disabled"


def test_evaluate_env_mismatch(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "F", "environments": ["production"]})
    resp = c.post("/flags/flag/evaluate", json={"user_id": "alice", "environment": "staging"})
    assert resp.get_json()["reason"] == "environment_mismatch"


def test_evaluate_allowlist(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "F", "allowlist": ["alice"]})
    resp = c.post("/flags/flag/evaluate", json={"user_id": "alice"})
    data = resp.get_json()
    assert data["enabled"] is True
    assert data["reason"] == "allowlist"


def test_evaluate_allowlist_bypasses_environment(client):
    """Allowlisted user is enabled even when environment doesn't match."""
    c, _ = client
    c.post("/flags", json={
        "key": "flag", "name": "F",
        "allowlist": ["alice"], "environments": ["production"],
    })
    resp = c.post("/flags/flag/evaluate", json={"user_id": "alice", "environment": "staging"})
    data = resp.get_json()
    assert data["enabled"] is True
    assert data["reason"] == "allowlist"


def test_evaluate_percentage_100(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "F", "percentage": 100})
    resp = c.post("/flags/flag/evaluate", json={"user_id": "alice"})
    data = resp.get_json()
    assert data["enabled"] is True
    assert data["reason"] == "percentage"


def test_evaluate_percentage_0(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "F", "percentage": 0})
    resp = c.post("/flags/flag/evaluate", json={"user_id": "alice"})
    data = resp.get_json()
    assert data["enabled"] is False
    assert data["reason"] == "percentage"


def test_evaluate_increments_eval_count(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "F"})
    for _ in range(3):
        c.post("/flags/flag/evaluate", json={"user_id": "alice"})
    resp = c.get("/flags/flag")
    assert resp.get_json()["eval_count"] == 3


def test_evaluate_determinism_via_route(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "F", "percentage": 50})
    results = [
        c.post("/flags/flag/evaluate", json={"user_id": "alice"}).get_json()["enabled"]
        for _ in range(5)
    ]
    assert len(set(results)) == 1


def test_evaluate_flag_not_found_404(client):
    c, _ = client
    assert c.post("/flags/missing/evaluate", json={"user_id": "alice"}).status_code == 404


def test_evaluate_missing_user_id_400(client):
    c, _ = client
    c.post("/flags", json={"key": "flag", "name": "F"})
    resp = c.post("/flags/flag/evaluate", json={})
    assert resp.status_code == 400


def test_evaluate_dependency_chain(client):
    c, db_path = client
    c.post("/flags", json={"key": "gate", "name": "Gate", "enabled": False})
    c.post("/flags", json={"key": "feature", "name": "Feature", "default_enabled": True})
    add_dependency("feature", "gate", db_path=db_path)
    resp = c.post("/flags/feature/evaluate", json={"user_id": "alice"})
    data = resp.get_json()
    assert data["enabled"] is False
    assert data["reason"] == "dependency_disabled"
    assert data["dependency"] == "gate"


# ── POST /flags/<key>/dependencies ────────────────────────────────────────────

def test_add_dependency_201(client):
    c, _ = client
    c.post("/flags", json={"key": "a", "name": "A"})
    c.post("/flags", json={"key": "b", "name": "B"})
    resp = c.post("/flags/a/dependencies", json={"depends_on_key": "b"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["flag_key"] == "a"
    assert data["depends_on_key"] == "b"


def test_add_dependency_cycle_409(client):
    c, _ = client
    c.post("/flags", json={"key": "a", "name": "A"})
    c.post("/flags", json={"key": "b", "name": "B"})
    c.post("/flags/a/dependencies", json={"depends_on_key": "b"})
    resp = c.post("/flags/b/dependencies", json={"depends_on_key": "a"})
    assert resp.status_code == 409


def test_add_dependency_flag_not_found_404(client):
    c, _ = client
    c.post("/flags", json={"key": "a", "name": "A"})
    resp = c.post("/flags/a/dependencies", json={"depends_on_key": "nonexistent"})
    assert resp.status_code == 404


def test_add_dependency_missing_field_400(client):
    c, _ = client
    c.post("/flags", json={"key": "a", "name": "A"})
    resp = c.post("/flags/a/dependencies", json={})
    assert resp.status_code == 400


# ── DELETE /flags/<key>/dependencies/<dep> ────────────────────────────────────

def test_remove_dependency_204(client):
    c, _ = client
    c.post("/flags", json={"key": "a", "name": "A"})
    c.post("/flags", json={"key": "b", "name": "B"})
    c.post("/flags/a/dependencies", json={"depends_on_key": "b"})
    resp = c.delete("/flags/a/dependencies/b")
    assert resp.status_code == 204


def test_remove_dependency_not_found_404(client):
    c, _ = client
    c.post("/flags", json={"key": "a", "name": "A"})
    c.post("/flags", json={"key": "b", "name": "B"})
    resp = c.delete("/flags/a/dependencies/b")
    assert resp.status_code == 404
