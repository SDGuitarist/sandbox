import sqlite3

from flask import Blueprint, current_app, jsonify, request

from .db import ChecksumMismatchError, MigrationLockError
from .files import MigrationFileError
from .runner import migrate_down, migrate_up, migration_status

bp = Blueprint("migrator", __name__)


def _db():
    return current_app.config.get("DB_PATH")


def _migrations_dir():
    return current_app.config.get("MIGRATIONS_DIR")


@bp.route("/migrate/up", methods=["POST"])
def up_route():
    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get("dry_run", False))
    target = body.get("target")

    if target is not None and not isinstance(target, str):
        return jsonify({"error": "target must be a string version (e.g. '0002')"}), 400

    try:
        result = migrate_up(
            _db(), _migrations_dir(),
            dry_run=dry_run, target=target, locked_by="api"
        )
        return jsonify(result), 200
    except MigrationLockError as e:
        return jsonify({"error": str(e)}), 409
    except ChecksumMismatchError as e:
        return jsonify({"error": str(e)}), 409
    except MigrationFileError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/migrate/down", methods=["POST"])
def down_route():
    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get("dry_run", False))
    steps = body.get("steps", 1)

    try:
        steps = int(steps)
        if steps < 1:
            return jsonify({"error": "steps must be >= 1"}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "steps must be an integer >= 1"}), 400

    try:
        result = migrate_down(
            _db(), _migrations_dir(),
            steps=steps, dry_run=dry_run, locked_by="api"
        )
        return jsonify(result), 200
    except MigrationLockError as e:
        return jsonify({"error": str(e)}), 409
    except ChecksumMismatchError as e:
        return jsonify({"error": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except MigrationFileError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/migrate/status", methods=["GET"])
def status_route():
    try:
        result = migration_status(_db(), _migrations_dir())
        return jsonify(result), 200
    except MigrationFileError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/migrate/lock", methods=["DELETE"])
def force_release_lock_route():
    """Admin endpoint to force-release a stale lock (e.g., after a crashed migration)."""
    from .db import get_db
    try:
        with get_db(path=_db(), immediate=True) as conn:
            conn.execute("DELETE FROM migrations_lock WHERE id = 1")
        return jsonify({"released": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
