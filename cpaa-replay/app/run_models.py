"""State machine for replay_runs (SOLE writer of the table)."""

import secrets
import sqlite3


def start_run(conn: sqlite3.Connection) -> tuple[str, bool]:
    run_id = secrets.token_hex(4)
    cur = conn.execute(
        "INSERT INTO replay_runs(run_id, status, started_at) "
        "SELECT ?, 'RUNNING', datetime('now') "
        "WHERE NOT EXISTS (SELECT 1 FROM replay_runs WHERE status = 'RUNNING')",
        (run_id,),
    )
    if cur.rowcount == 1:
        return run_id, True
    active = active_run(conn)
    return active, False


def active_run(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT run_id FROM replay_runs WHERE status = 'RUNNING' LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return row["run_id"]


def mark_complete_pass(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    events_applied: int,
    projection_hash: str,
    live_hash_pre: str,
    live_hash_post: str,
) -> None:
    conn.execute(
        "UPDATE replay_runs SET status = 'COMPLETE_PASS', events_applied = ?, "
        "projection_hash = ?, live_hash_pre = ?, live_hash_post = ?, "
        "reset_done = 1, finished_at = datetime('now') WHERE run_id = ?",
        (events_applied, projection_hash, live_hash_pre, live_hash_post, run_id),
    )


def mark_aborted(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute(
        "UPDATE replay_runs SET status = 'ABORTED', "
        "finished_at = datetime('now') WHERE run_id = ?",
        (run_id,),
    )


def reap_stale_runs(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "UPDATE replay_runs SET status = 'ABORTED', "
        "finished_at = datetime('now') "
        "WHERE status = 'RUNNING' AND finished_at IS NULL "
        "AND started_at < datetime('now', '-15 minutes')"
    )
    return cur.rowcount
