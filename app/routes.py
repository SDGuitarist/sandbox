from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from .db import append_event, get_events, get_projection

bp = Blueprint("audit", __name__)

REQUIRED_EVENT_FIELDS = ("entity_id", "entity_type", "event_type", "payload")
TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def _db_path():
    return current_app.config.get("DB_PATH")


def _parse_timestamp(value, field_name):
    """Return (value, error_response). Validates 'YYYY-MM-DD HH:MM:SS' format."""
    try:
        datetime.strptime(value, TS_FORMAT)
        return value, None
    except ValueError:
        return None, (jsonify({"error": f"'{field_name}' must be 'YYYY-MM-DD HH:MM:SS'"}), 400)


@bp.route("/events", methods=["POST"])
def create_event():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body must be JSON"}), 400

    missing = [f for f in REQUIRED_EVENT_FIELDS if f not in body]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    payload = body["payload"]
    if not isinstance(payload, dict):
        return jsonify({"error": "'payload' must be a JSON object"}), 400

    actor_raw = body.get("actor")
    actor = str(actor_raw) if actor_raw is not None else None

    event = append_event(
        entity_id=str(body["entity_id"]),
        entity_type=str(body["entity_type"]),
        event_type=str(body["event_type"]),
        payload_dict=payload,
        actor=actor,
        db_path=_db_path(),
    )
    if isinstance(event.get("payload"), str):
        import json
        event["payload"] = json.loads(event["payload"])
    return jsonify(event), 201


@bp.route("/events", methods=["GET"])
def list_events():
    entity_id = request.args.get("entity_id")
    entity_type = request.args.get("entity_type")
    event_type = request.args.get("event_type")
    since_raw = request.args.get("since")
    before_raw = request.args.get("before")
    after_raw = request.args.get("after")
    limit_raw = request.args.get("limit", 50)

    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "'limit' must be an integer"}), 400

    after_id = None
    if after_raw is not None:
        try:
            after_id = int(after_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "'after' must be an integer cursor"}), 400

    since = None
    if since_raw is not None:
        since, err = _parse_timestamp(since_raw, "since")
        if err:
            return err

    before = None
    if before_raw is not None:
        before, err = _parse_timestamp(before_raw, "before")
        if err:
            return err

    events, next_cursor = get_events(
        entity_id=entity_id,
        entity_type=entity_type,
        event_type=event_type,
        after_id=after_id,
        before=before,
        since=since,
        limit=limit,
        db_path=_db_path(),
    )
    return jsonify({"events": events, "next_cursor": next_cursor}), 200


@bp.route("/entities/<entity_id>/events", methods=["GET"])
def entity_events(entity_id):
    """Shorthand: GET /events filtered by entity_id."""
    after_raw = request.args.get("after")
    limit_raw = request.args.get("limit", 50)

    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "'limit' must be an integer"}), 400

    after_id = None
    if after_raw is not None:
        try:
            after_id = int(after_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "'after' must be an integer cursor"}), 400

    events, next_cursor = get_events(
        entity_id=entity_id,
        after_id=after_id,
        limit=limit,
        db_path=_db_path(),
    )
    return jsonify({"events": events, "next_cursor": next_cursor}), 200


@bp.route("/entities/<entity_id>/projection", methods=["GET"])
def entity_projection(entity_id):
    proj = get_projection(entity_id, db_path=_db_path())
    if proj is None:
        return jsonify({"error": f"No projection found for entity '{entity_id}'"}), 404
    return jsonify(proj), 200


@bp.route("/entities/<entity_id>/history", methods=["GET"])
def entity_history(entity_id):
    """Return full event history for an entity, ascending by id (no pagination)."""
    db_path = _db_path()
    events, cursor = get_events(entity_id=entity_id, limit=200, db_path=db_path)
    all_events = list(events)
    while cursor is not None:
        events, cursor = get_events(entity_id=entity_id, after_id=cursor, limit=200, db_path=db_path)
        all_events.extend(events)
    return jsonify({"events": all_events}), 200
