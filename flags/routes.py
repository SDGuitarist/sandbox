import json
import re
import sqlite3

from flask import Blueprint, current_app, jsonify, request

from .db import (
    add_dependency,
    create_flag,
    delete_flag,
    evaluate_flag,
    get_dependencies,
    get_flag,
    list_flags,
    remove_dependency,
    update_flag,
)

bp = Blueprint("flags", __name__)

_VALID_UPDATE_KEYS = frozenset(
    {"name", "description", "enabled", "default_enabled", "environments", "allowlist", "percentage"}
)


def _db():
    return current_app.config.get("DB_PATH")


def _validate_percentage(value):
    """Return (value, error_string). value may be None (disables percentage)."""
    if value is None:
        return None, None
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None, "percentage must be an integer 0-100 or null"
    if not (0 <= v <= 100):
        return None, "percentage must be between 0 and 100"
    return v, None


_FLAG_KEY_RE = re.compile(r'^[a-zA-Z0-9_.:-]{1,200}$')


def _validate_json_list(value, field_name):
    """Validate that value is a list (of strings) or None. Returns (value, error_string)."""
    if value is None:
        return None, None
    if not isinstance(value, list):
        return None, f"{field_name} must be a list or null"
    if not all(isinstance(item, str) for item in value):
        return None, f"{field_name} items must all be strings"
    return value, None


# ── Flags CRUD ────────────────────────────────────────────────────────────────

@bp.route("/flags", methods=["POST"])
def create_flag_route():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body must be JSON"}), 400

    key = str(body.get("key", "")).strip()
    name = str(body.get("name", "")).strip()
    if not key:
        return jsonify({"error": "Missing required field: key"}), 400
    if not _FLAG_KEY_RE.match(key):
        return jsonify({"error": "key must be 1-200 chars: letters, digits, _ . : -"}), 400
    if not name:
        return jsonify({"error": "Missing required field: name"}), 400

    percentage, err = _validate_percentage(body.get("percentage"))
    if err:
        return jsonify({"error": err}), 400

    environments, err = _validate_json_list(body.get("environments"), "environments")
    if err:
        return jsonify({"error": err}), 400

    allowlist, err = _validate_json_list(body.get("allowlist"), "allowlist")
    if err:
        return jsonify({"error": err}), 400

    try:
        flag = create_flag(
            key=key,
            name=name,
            description=body.get("description"),
            enabled=bool(body.get("enabled", True)),
            default_enabled=bool(body.get("default_enabled", False)),
            environments=environments,
            allowlist=allowlist,
            percentage=percentage,
            db_path=_db(),
        )
        return jsonify(flag), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Flag key '{key}' already exists"}), 409


@bp.route("/flags", methods=["GET"])
def list_flags_route():
    return jsonify({"flags": list_flags(db_path=_db())}), 200


@bp.route("/flags/<key>", methods=["GET"])
def get_flag_route(key):
    flag = get_flag(key, db_path=_db())
    if flag is None:
        return jsonify({"error": f"Flag '{key}' not found"}), 404
    flag["dependencies"] = get_dependencies(key, db_path=_db())
    return jsonify(flag), 200


@bp.route("/flags/<key>", methods=["PATCH"])
def update_flag_route(key):
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body must be JSON"}), 400

    updates = {k: v for k, v in body.items() if k in _VALID_UPDATE_KEYS}

    if "percentage" in updates:
        pct, err = _validate_percentage(updates["percentage"])
        if err:
            return jsonify({"error": err}), 400
        updates["percentage"] = pct

    if "environments" in updates:
        envs, err = _validate_json_list(updates["environments"], "environments")
        if err:
            return jsonify({"error": err}), 400
        updates["environments"] = envs

    if "allowlist" in updates:
        alist, err = _validate_json_list(updates["allowlist"], "allowlist")
        if err:
            return jsonify({"error": err}), 400
        updates["allowlist"] = alist

    result = update_flag(key, updates, db_path=_db())
    if result is None:
        return jsonify({"error": f"Flag '{key}' not found"}), 404
    return jsonify(result), 200


@bp.route("/flags/<key>", methods=["DELETE"])
def delete_flag_route(key):
    if not delete_flag(key, db_path=_db()):
        return jsonify({"error": f"Flag '{key}' not found"}), 404
    return "", 204


# ── Evaluation ────────────────────────────────────────────────────────────────

@bp.route("/flags/<key>/evaluate", methods=["POST"])
def evaluate_flag_route(key):
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = str(body.get("user_id", "")).strip()
    if not user_id:
        return jsonify({"error": "Missing required field: user_id"}), 400

    environment = body.get("environment")

    result = evaluate_flag(key, user_id, environment=environment, db_path=_db())
    if result["reason"] == "not_found":
        return jsonify({"error": f"Flag '{key}' not found"}), 404
    return jsonify(result), 200


# ── Dependencies ──────────────────────────────────────────────────────────────

@bp.route("/flags/<key>/dependencies", methods=["POST"])
def add_dependency_route(key):
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body must be JSON"}), 400

    dep_key = str(body.get("depends_on_key", "")).strip()
    if not dep_key:
        return jsonify({"error": "Missing required field: depends_on_key"}), 400

    if get_flag(key, db_path=_db()) is None:
        return jsonify({"error": f"Flag '{key}' not found"}), 404
    if get_flag(dep_key, db_path=_db()) is None:
        return jsonify({"error": f"Dependency flag '{dep_key}' not found"}), 404

    try:
        add_dependency(key, dep_key, db_path=_db())
        return jsonify({"flag_key": key, "depends_on_key": dep_key}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except sqlite3.IntegrityError:
        return jsonify({"error": "Dependency already exists"}), 409


@bp.route("/flags/<key>/dependencies/<dep_key>", methods=["DELETE"])
def remove_dependency_route(key, dep_key):
    if not remove_dependency(key, dep_key, db_path=_db()):
        return jsonify({"error": f"Dependency '{key}' → '{dep_key}' not found"}), 404
    return "", 204
