"""Payload parsing + ingest-time structural validation (B1-payload).

Two responsibilities:
1. parse_json / parse_patch -- JSON parsing and PRESENT-KEYS-ONLY PATCH merge
   helpers used by ingest and the proj_* apply handlers.
2. validate_event -- ingest-time structural validation (spec sec.7 last row):
   every source event is checked BEFORE it is appended to the events log.
"""

import json

from app.constants import DISPATCH

# Maximum size of a single source-event payload (spec sec.7: payload <=64KB).
MAX_PAYLOAD_BYTES = 64 * 1024
# Maximum length of an event_type string (spec sec.7: non-empty str <=128).
MAX_EVENT_TYPE_LEN = 128

# Required PK key per event_type (spec sec.4.4 "Required" column). An event whose
# payload is missing its required key is malformed and skipped at ingest time.
# Event types whose only required keys are non-PK data keys (sec.4.4) have their
# PK requirement satisfied by an empty tuple here; full apply-time rules live in
# the proj_* handlers.
_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "system.heartbeat": ("station_id",),
    "telemetry.culinary.weight": ("station_id",),
    "telemetry.culinary.temperature": ("station_id",),
    "telemetry.financial.transaction": ("station_id",),
    "telemetry.financial.bid": ("lot_id",),
    "telemetry.environmental.weather": (),
    "system.operator_note": ("note",),
    "system.alert.raised": ("alert_type", "source"),
    "system.alert.resolved": ("alert_key",),
}


def parse_json(raw: str) -> dict | None:
    """Parse `raw` JSON text; return the dict iff it is a valid JSON object.

    Returns None for invalid JSON OR for any valid-but-non-object JSON value
    (list, string, number, bool, null). Callers treat None as malformed.
    """
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def parse_patch(payload: dict, allowed: tuple) -> dict[str, object | None]:
    """PRESENT-KEYS-ONLY PATCH merge (frozen sec.3.1 #5, sec.8.7).

    Returns a dict of ONLY the keys present in `payload` that are also in
    `allowed`, mapping each to its value with explicit JSON null -> Python None.
    Absent keys are omitted entirely (no sentinel), so the caller leaves the
    corresponding column unchanged. Keys not in `allowed` are dropped here; the
    handler records the unknown_key anomaly.
    """
    return {key: payload[key] for key in allowed if key in payload}


def validate_event(event_type: object, payload_text: str) -> tuple[bool, str | None, str | None]:
    """Ingest-time structural validation (spec sec.7 last row).

    Validates a single source event BEFORE it is appended to the events log:
      - `event_type` is a non-empty str of length <= 128 AND present in DISPATCH;
      - `payload_text` is <= 64KB;
      - `payload_text` parses to a JSON object (dict);
      - the required PK key(s) for the event_type (sec.4.4) are present.

    Returns `(ok, kind, detail)`:
      - ok=True  -> (True, None, None): event is structurally valid, append it.
      - ok=False -> (False, kind, detail): event is SKIPPED. `kind` is the
        anomaly kind to record:
          'unknown_key'       when event_type is not in DISPATCH
                              (detail='unmapped event_type');
          'malformed_payload' for every other structural failure
                              (bad event_type, oversize, non-object, missing PK).
    """
    if not isinstance(event_type, str) or not event_type or len(event_type) > MAX_EVENT_TYPE_LEN:
        return (False, "malformed_payload", "invalid event_type")

    if event_type not in DISPATCH:
        return (False, "unknown_key", "unmapped event_type")

    if len(payload_text.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        return (False, "malformed_payload", "payload exceeds size cap")

    parsed = parse_json(payload_text)
    if parsed is None:
        return (False, "malformed_payload", "payload is not a JSON object")

    for key in _REQUIRED_KEYS[event_type]:
        if key not in parsed:
            return (False, "malformed_payload", f"missing required key: {key}")

    return (True, None, None)
