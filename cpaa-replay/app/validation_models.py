import sqlite3

from app.constants import _PROJECTION_TABLES


def record_determinism(
    conn: sqlite3.Connection,
    run_a: str,
    run_b: str,
    match: int,
    diffs: list[dict],
) -> int:
    cur = conn.execute(
        "INSERT INTO determinism_results(run_a, run_b, match) VALUES (?, ?, ?)",
        (run_a, run_b, match),
    )
    result_id = cur.lastrowid

    table_order = {name: i for i, name in enumerate(_PROJECTION_TABLES)}
    ordered = sorted(
        diffs,
        key=lambda d: (
            table_order.get(d["table_name"], len(table_order)),
            d["pk"],
            d["key"],
        ),
    )
    for d in ordered:
        conn.execute(
            "INSERT INTO determinism_diffs"
            "(result_id, table_name, pk, key, value_a, value_b)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                result_id,
                d["table_name"],
                d["pk"],
                d["key"],
                d["value_a"],
                d["value_b"],
            ),
        )

    return result_id
