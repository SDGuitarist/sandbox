import re

TS_FORMAT = "%Y-%m-%d %H:%M:%S"
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

RUN_STATES = ("PENDING", "RUNNING", "COMPLETE_PASS", "ABORTED")

ANOMALY_KINDS = ("dup_conflict", "unknown_key", "malformed_payload")

_PROJECTION_TABLES = (
    "station_state",
    "auction_state",
    "environmental_state",
    "system_state",
)

DISPATCH = {
    "system.heartbeat": "proj_station",
    "telemetry.culinary.weight": "proj_station",
    "telemetry.culinary.temperature": "proj_station",
    "telemetry.financial.transaction": "proj_station",
    "telemetry.financial.bid": "proj_auction",
    "telemetry.environmental.weather": "proj_environmental",
    "system.operator_note": "proj_system",
    "system.alert.raised": "proj_system",
    "system.alert.resolved": "proj_system",
}

EMPTY_PROJECTION_HASH = "0000000000000000000000000000000000000000000000000000000000000000"
