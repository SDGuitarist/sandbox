from __future__ import annotations

import sqlite3

from flask import Blueprint, jsonify

from app import login_required
from flask import current_app

from app.db import get_db
from app.ingest import ingest_source
from app.run_models import active_run, reap_stale_runs

ingest_bp = Blueprint("ingest", __name__, url_prefix="/ingest")


@ingest_bp.route("/run", methods=["POST"])
@login_required
def run_ingest():
    try:
        with get_db(immediate=True) as conn:
            reap_stale_runs(conn)
            running = active_run(conn)
            if running is not None:
                return jsonify({"error": "a run is active", "run_id": running}), 409
            ingest_source(conn, current_app.config['LIVE_DB'])
        return jsonify({"status": "ok"}), 200
    except sqlite3.Error:
        return jsonify({"error": "internal error"}), 503
