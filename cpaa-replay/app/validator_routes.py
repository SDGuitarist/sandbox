"""Validator blueprint: determinism comparison + result lookup.

POST /validate/run compares two completed runs (run_a, run_b) and records the
determinism verdict + field-level diffs. GET /validate/<int:result_id> returns a
stored result with its diffs. Static-literal route registered before the
<converter> route.
"""

from __future__ import annotations

import re
import sqlite3

from flask import Blueprint, current_app, jsonify, request

from app import login_required
from app.db import get_db, open_live_ro
from app.validator import validate_runs

validate_bp = Blueprint("validate", __name__)

_RUN_ID_RE = re.compile(r"^[0-9a-f]{8}$")


@validate_bp.route("/run", methods=["POST"])
@login_required
def run():
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400

    run_a = body.get("run_a")
    run_b = body.get("run_b")
    for name, value in (("run_a", run_a), ("run_b", run_b)):
        if not isinstance(value, str) or not _RUN_ID_RE.match(value):
            return (
                jsonify(
                    {"error": f"{name} must match ^[0-9a-f]{{8}}$"}
                ),
                400,
            )
    if run_a == run_b:
        return jsonify({"error": "run_a and run_b must differ"}), 400

    try:
        with get_db(immediate=True) as conn:
            for name, value in (("run_a", run_a), ("run_b", run_b)):
                row = conn.execute(
                    "SELECT status FROM replay_runs WHERE run_id = ?",
                    (value,),
                ).fetchone()
                if row is None:
                    return jsonify({"error": f"{name} not found"}), 404
                if row["status"] != "COMPLETE_PASS":
                    return (
                        jsonify(
                            {"error": f"{name} is not COMPLETE_PASS"}
                        ),
                        409,
                    )

            live_ro = open_live_ro(current_app.config["LIVE_DB"])
            try:
                result_id = validate_runs(conn, run_a, run_b, live_ro)
            finally:
                live_ro.close()
        return jsonify({"result_id": result_id}), 200
    except sqlite3.Error:
        return jsonify({"error": "internal error"}), 503


@validate_bp.route("/<int:result_id>", methods=["GET"])
@login_required
def detail(result_id: int):
    with get_db() as conn:
        result = conn.execute(
            "SELECT id, run_a, run_b, match, created_at "
            "FROM determinism_results WHERE id = ?",
            (result_id,),
        ).fetchone()
        if result is None:
            return jsonify({"error": "result not found"}), 404
        diff_rows = conn.execute(
            "SELECT table_name, pk, key, value_a, value_b "
            "FROM determinism_diffs WHERE result_id = ? ORDER BY id ASC",
            (result_id,),
        ).fetchall()
    diffs = [
        {
            "table_name": row["table_name"],
            "pk": row["pk"],
            "key": row["key"],
            "value_a": row["value_a"],
            "value_b": row["value_b"],
        }
        for row in diff_rows
    ]
    return jsonify(
        {
            "result_id": result["id"],
            "run_a": result["run_a"],
            "run_b": result["run_b"],
            "match": result["match"],
            "created_at": result["created_at"],
            "diffs": diffs,
        }
    )
