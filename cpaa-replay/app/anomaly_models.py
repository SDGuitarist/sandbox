"""Single writer of the anomalies table.

record_anomaly participates in the caller's transaction (never commits,
never opens its own) and never raises (a logging failure must not break
the caller's flow).
"""

import sqlite3

from app.constants import ANOMALY_KINDS


def record_anomaly(
    conn: sqlite3.Connection,
    run_id: str | None,
    kind: str,
    idempotency_key: str | None,
    detail: str | None,
) -> None:
    if kind not in ANOMALY_KINDS:
        return
    try:
        conn.execute(
            "INSERT INTO anomalies(run_id, kind, idempotency_key, detail) "
            "VALUES(?, ?, ?, ?)",
            (run_id, kind, idempotency_key, detail),
        )
    except sqlite3.Error:
        return
