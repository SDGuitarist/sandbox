"""PATCH-merge semantics tests (frozen #5, §8.7) — verify-first.

Covers: explicit null clears a nullable column, absent key leaves it
unchanged, an additive NOT NULL counter treats present-null as a no-op (not a
clear), and an unknown key at apply-time records an `unknown_key` anomaly while
canonical columns stay untouched.
"""
from app.event_models import append_event
from app.payload import parse_patch
from app.proj_station import apply_station, reset_station


_TS = "2026-06-15 19:00:00"
_ALLOWED = ("weight_kg", "temp_c")


# ---------------------------------------------------------------------------
# parse_patch: the present-keys-only contract (null -> None, absent omitted)
# ---------------------------------------------------------------------------
def test_parse_patch_present_value_is_kept():
    out = parse_patch({"weight_kg": 12.5}, _ALLOWED)
    assert out == {"weight_kg": 12.5}


def test_parse_patch_explicit_null_becomes_none():
    out = parse_patch({"weight_kg": None}, _ALLOWED)
    assert "weight_kg" in out
    assert out["weight_kg"] is None


def test_parse_patch_absent_key_is_omitted():
    out = parse_patch({"temp_c": 4.0}, _ALLOWED)
    assert "weight_kg" not in out, "absent key must NOT appear in the result"
    assert out == {"temp_c": 4.0}


def test_parse_patch_only_returns_allowed_keys():
    out = parse_patch({"weight_kg": 1.0, "bogus": 9}, _ALLOWED)
    assert "bogus" not in out


# ---------------------------------------------------------------------------
# handler-level: null clears, absent unchanged
# ---------------------------------------------------------------------------
def _event_row(conn, key, event_type, payload_json):
    eid = append_event(conn, key, _TS, event_type, payload_json, "gen")
    return conn.execute(
        "SELECT * FROM events WHERE event_id = ?", (eid,)
    ).fetchone()


def _station(conn, station_id):
    return conn.execute(
        "SELECT * FROM station_state WHERE station_id = ?", (station_id,)
    ).fetchone()


def test_null_clears_nullable_column(shadow_conn):
    reset_station(shadow_conn)
    # set weight_kg first
    apply_station(
        shadow_conn,
        _event_row(shadow_conn, "w1", "telemetry.culinary.weight",
                   '{"station_id":"S1","weight_kg":10.0}'),
    )
    assert _station(shadow_conn, "S1")["weight_kg"] == 10.0
    # explicit null clears it
    apply_station(
        shadow_conn,
        _event_row(shadow_conn, "w2", "telemetry.culinary.weight",
                   '{"station_id":"S1","weight_kg":null}'),
    )
    assert _station(shadow_conn, "S1")["weight_kg"] is None


def test_absent_key_leaves_column_unchanged(shadow_conn):
    reset_station(shadow_conn)
    apply_station(
        shadow_conn,
        _event_row(shadow_conn, "t1", "telemetry.culinary.temperature",
                   '{"station_id":"S1","temp_c":4.0}'),
    )
    apply_station(
        shadow_conn,
        _event_row(shadow_conn, "w1", "telemetry.culinary.weight",
                   '{"station_id":"S1","weight_kg":3.0}'),
    )
    row = _station(shadow_conn, "S1")
    # the weight event did not carry temp_c, so it must be unchanged
    assert row["temp_c"] == 4.0
    assert row["weight_kg"] == 3.0


def test_additive_counter_null_is_noop_not_clear(shadow_conn):
    reset_station(shadow_conn)
    apply_station(
        shadow_conn,
        _event_row(shadow_conn, "tx1", "telemetry.financial.transaction",
                   '{"station_id":"S1","amount_cents":500}'),
    )
    assert _station(shadow_conn, "S1")["sales_total_cents"] == 500
    # present-null on a NOT NULL additive counter -> no-op (NOT a clear, NOT 0)
    apply_station(
        shadow_conn,
        _event_row(shadow_conn, "tx2", "telemetry.financial.transaction",
                   '{"station_id":"S1","amount_cents":null}'),
    )
    assert _station(shadow_conn, "S1")["sales_total_cents"] == 500


def test_unknown_key_records_anomaly_and_leaves_columns_untouched(shadow_conn):
    reset_station(shadow_conn)
    apply_station(
        shadow_conn,
        _event_row(shadow_conn, "u1", "telemetry.culinary.weight",
                   '{"station_id":"S1","weight_kg":7.0}'),
    )
    before = _station(shadow_conn, "S1")["weight_kg"]
    # a key outside the event type's allowed set -> unknown_key anomaly
    apply_station(
        shadow_conn,
        _event_row(shadow_conn, "u2", "telemetry.culinary.weight",
                   '{"station_id":"S1","not_a_real_key":1}'),
    )
    anomalies = shadow_conn.execute(
        "SELECT * FROM anomalies WHERE kind = 'unknown_key'"
    ).fetchall()
    assert len(anomalies) >= 1
    # canonical column untouched by the unknown key
    assert _station(shadow_conn, "S1")["weight_kg"] == before
