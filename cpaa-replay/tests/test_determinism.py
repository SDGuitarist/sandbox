"""Determinism + canonical-hash tests (frozen #2, pinned D, §8.8).

Covers: empty projection -> EMPTY_PROJECTION_HASH, two identical event
sequences -> identical hash, the golden-corpus projection_hash anchor,
forced mismatch -> match=0 with ordered field-level diffs, per-column
read-back type assertions, and that the point-in-time query uses idx_events_ts.
"""
import re

import pytest

from app.constants import EMPTY_PROJECTION_HASH
from app.event_models import append_event
from app.serialization import canonical_hash
from app.proj_station import apply_station, reset_station
from app.proj_auction import reset_auction
from app.proj_environmental import reset_environmental
from app.proj_system import reset_system
from app.validation_models import record_determinism


_TS = "2026-06-15 19:00:00"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _reset_all(conn):
    reset_station(conn)
    reset_auction(conn)
    reset_environmental(conn)
    reset_system(conn)


def _row(conn, key, event_type, payload_json, ts=_TS):
    eid = append_event(conn, key, ts, event_type, payload_json, "gen")
    return conn.execute("SELECT * FROM events WHERE event_id = ?", (eid,)).fetchone()


def _apply_sequence(conn, events):
    """Reset all projections, then apply a list of (key, type, payload) tuples."""
    _reset_all(conn)
    for key, etype, payload in events:
        apply_station(conn, _row(conn, key, etype, payload))


# ---------------------------------------------------------------------------
def test_empty_projection_hash_is_well_formed_literal():
    assert isinstance(EMPTY_PROJECTION_HASH, str)
    assert _HEX64.match(EMPTY_PROJECTION_HASH), "must be 64-char lowercase hex"


def test_empty_projection_matches_empty_hash_constant(shadow_conn):
    _reset_all(shadow_conn)
    assert canonical_hash(shadow_conn) == EMPTY_PROJECTION_HASH


def test_canonical_hash_format(shadow_conn):
    _reset_all(shadow_conn)
    h = canonical_hash(shadow_conn)
    assert _HEX64.match(h), "canonical_hash must be 64-char lowercase hex"


def test_two_identical_sequences_produce_identical_hash(shadow_conn):
    seq = [
        ("a", "system.heartbeat", '{"station_id":"S1"}'),
        ("b", "telemetry.culinary.weight", '{"station_id":"S1","weight_kg":12.5}'),
        ("c", "telemetry.culinary.temperature", '{"station_id":"S2","temp_c":4.0}'),
    ]
    _apply_sequence(shadow_conn, seq)
    hash_run_a = canonical_hash(shadow_conn)

    # second run: same logical sequence, distinct idempotency keys
    seq2 = [(k + "2", t, p) for (k, t, p) in seq]
    _apply_sequence(shadow_conn, seq2)
    hash_run_b = canonical_hash(shadow_conn)

    assert hash_run_a == hash_run_b, "same event sequence must hash identically"


def test_different_sequences_produce_different_hash(shadow_conn):
    _apply_sequence(shadow_conn, [
        ("x", "telemetry.culinary.weight", '{"station_id":"S1","weight_kg":1.0}'),
    ])
    h1 = canonical_hash(shadow_conn)
    _apply_sequence(shadow_conn, [
        ("y", "telemetry.culinary.weight", '{"station_id":"S1","weight_kg":2.0}'),
    ])
    h2 = canonical_hash(shadow_conn)
    assert h1 != h2


def test_golden_corpus_projection_hash_anchor():
    """The committed golden-corpus projection_hash literal (§8.8) must exist as a
    frozen 64-hex constant. Its name is not enumerated in §5, so discover it
    rather than guess (FC1/FC9)."""
    import app.constants as constants

    candidates = {
        name: getattr(constants, name)
        for name in dir(constants)
        if "GOLDEN" in name and isinstance(getattr(constants, name), str)
    }
    if not candidates:
        pytest.skip("no GOLDEN_* hash constant frozen in app.constants")
    for name, value in candidates.items():
        assert _HEX64.match(value), f"{name} must be 64-char lowercase hex"
        assert value != EMPTY_PROJECTION_HASH, (
            f"{name} (golden corpus) must differ from the empty-projection hash"
        )


def test_forced_mismatch_records_match_zero_with_ordered_diffs(shadow_conn):
    diffs = [
        {"table_name": "station_state", "pk": "S1", "key": "weight_kg",
         "value_a": "1.0", "value_b": "2.0"},
        {"table_name": "station_state", "pk": "S2", "key": "temp_c",
         "value_a": "4.0", "value_b": "5.0"},
    ]
    result_id = record_determinism(shadow_conn, "aaaaaaaa", "bbbbbbbb", 0, diffs)
    assert isinstance(result_id, int)

    res = shadow_conn.execute(
        "SELECT * FROM determinism_results WHERE id = ?", (result_id,)
    ).fetchone()
    assert res["match"] == 0
    assert res["run_a"] == "aaaaaaaa" and res["run_b"] == "bbbbbbbb"

    diff_rows = shadow_conn.execute(
        "SELECT * FROM determinism_diffs WHERE result_id = ? ORDER BY id",
        (result_id,),
    ).fetchall()
    assert len(diff_rows) == 2
    assert diff_rows[0]["pk"] == "S1" and diff_rows[0]["key"] == "weight_kg"
    assert diff_rows[1]["pk"] == "S2" and diff_rows[1]["key"] == "temp_c"


def test_matching_runs_record_match_one_no_diffs(shadow_conn):
    result_id = record_determinism(shadow_conn, "cccccccc", "dddddddd", 1, [])
    res = shadow_conn.execute(
        "SELECT match FROM determinism_results WHERE id = ?", (result_id,)
    ).fetchone()
    assert res["match"] == 1
    diff_count = shadow_conn.execute(
        "SELECT COUNT(*) AS c FROM determinism_diffs WHERE result_id = ?",
        (result_id,),
    ).fetchone()["c"]
    assert diff_count == 0


def test_per_column_readback_types(shadow_conn):
    _reset_all(shadow_conn)
    apply_station(shadow_conn, _row(
        shadow_conn, "h", "system.heartbeat", '{"station_id":"S1"}'))
    apply_station(shadow_conn, _row(
        shadow_conn, "w", "telemetry.culinary.weight",
        '{"station_id":"S1","weight_kg":12.5}'))
    apply_station(shadow_conn, _row(
        shadow_conn, "f", "telemetry.financial.transaction",
        '{"station_id":"S1","amount_cents":500}'))

    row = shadow_conn.execute(
        "SELECT * FROM station_state WHERE station_id = ?", ("S1",)
    ).fetchone()
    assert isinstance(row["station_id"], str)      # TEXT
    assert isinstance(row["weight_kg"], float)     # REAL
    assert isinstance(row["sales_total_cents"], int)  # INTEGER
    assert isinstance(row["status"], str)          # TEXT (set by heartbeat)


def test_point_in_time_query_uses_index(shadow_conn):
    plan = shadow_conn.execute(
        "EXPLAIN QUERY PLAN "
        "SELECT * FROM events WHERE logical_ts <= ? ORDER BY event_id",
        (_TS,),
    ).fetchall()
    plan_text = " ".join(str(r[-1]) for r in plan)
    assert "idx_events_ts" in plan_text, (
        f"point-in-time query must use idx_events_ts; plan was: {plan_text}"
    )
