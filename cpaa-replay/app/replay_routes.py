import re
import sqlite3

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app import login_required
from app.constants import TS_RE
from app.db import get_db
from app.replay_engine import build_projection_at, run_replay

replay_bp = Blueprint("replay", __name__, url_prefix="/replay")

_RUN_ID_RE = re.compile(r"^[0-9a-f]{8}$")


@replay_bp.route("/run", methods=["POST"])
@login_required
def start():
    try:
        with get_db(immediate=True) as conn:
            run_id, acquired = run_replay(conn)
    except sqlite3.Error:
        return jsonify({"error": "internal error"}), 503
    if not acquired:
        return jsonify({"error": "a replay is already running", "run_id": run_id}), 409
    return redirect(url_for("replay.run_detail", run_id=run_id))


@replay_bp.route("/projection/at", methods=["GET"])
def projection_at():
    t = request.args.get("t", "")
    if not TS_RE.match(t):
        return jsonify({"error": "invalid t; expected YYYY-MM-DD HH:MM:SS"}), 400
    try:
        with get_db() as conn:
            projection = build_projection_at(conn, t)
    except sqlite3.Error:
        return jsonify({"error": "internal error"}), 503
    return render_template("projection.html", t=t, projection=projection)


@replay_bp.route("/run/<run_id>", methods=["GET"])
def run_detail(run_id):
    if not _RUN_ID_RE.match(run_id):
        return jsonify({"error": "run not found"}), 404
    try:
        with get_db() as conn:
            run = conn.execute(
                "SELECT * FROM replay_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            anomalies = conn.execute(
                "SELECT * FROM anomalies WHERE run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
    except sqlite3.Error:
        return jsonify({"error": "internal error"}), 503
    if run is None:
        return jsonify({"error": "run not found"}), 404
    return render_template("run_detail.html", run=run, anomalies=anomalies)
