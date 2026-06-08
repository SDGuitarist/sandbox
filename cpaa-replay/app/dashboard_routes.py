from flask import Blueprint, render_template

from app.db import get_db

dashboard_bp = Blueprint("dashboard", __name__)


def _read_dedup_counters(conn):
    counters = {"dup_exact": 0, "dup_conflict": 0}
    for row in conn.execute("SELECT kind, count FROM dedup_counters").fetchall():
        counters[row["kind"]] = row["count"]
    return counters


def _read_runs(conn):
    return conn.execute(
        "SELECT run_id, status, events_applied, projection_hash, "
        "live_hash_pre, live_hash_post, reset_done, started_at, finished_at "
        "FROM replay_runs ORDER BY started_at DESC, run_id DESC"
    ).fetchall()


def _read_projection_summary(conn):
    return {
        "station_state": conn.execute(
            "SELECT COUNT(*) AS c FROM station_state"
        ).fetchone()["c"],
        "auction_state": conn.execute(
            "SELECT COUNT(*) AS c FROM auction_state"
        ).fetchone()["c"],
        "environmental_state": conn.execute(
            "SELECT COUNT(*) AS c FROM environmental_state"
        ).fetchone()["c"],
        "system_state": conn.execute(
            "SELECT COUNT(*) AS c FROM system_state"
        ).fetchone()["c"],
    }


def _read_anomaly_count(conn):
    return conn.execute("SELECT COUNT(*) AS c FROM anomalies").fetchone()["c"]


def _read_determinism_results(conn):
    return conn.execute(
        "SELECT id, run_a, run_b, match, created_at "
        "FROM determinism_results ORDER BY id DESC"
    ).fetchall()


@dashboard_bp.route("/")
def index():
    with get_db() as conn:
        dedup_counters = _read_dedup_counters(conn)
        runs = _read_runs(conn)
        projection_summary = _read_projection_summary(conn)
        anomaly_count = _read_anomaly_count(conn)
        determinism_results = _read_determinism_results(conn)
    return render_template(
        "dashboard.html",
        dedup_counters=dedup_counters,
        runs=runs,
        projection_summary=projection_summary,
        anomaly_count=anomaly_count,
        determinism_results=determinism_results,
        view="overview",
    )


@dashboard_bp.route("/runs")
def runs():
    with get_db() as conn:
        dedup_counters = _read_dedup_counters(conn)
        runs = _read_runs(conn)
        projection_summary = _read_projection_summary(conn)
        anomaly_count = _read_anomaly_count(conn)
        determinism_results = _read_determinism_results(conn)
    return render_template(
        "dashboard.html",
        dedup_counters=dedup_counters,
        runs=runs,
        projection_summary=projection_summary,
        anomaly_count=anomaly_count,
        determinism_results=determinism_results,
        view="runs",
    )
