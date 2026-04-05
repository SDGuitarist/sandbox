import sqlite3

from flask import Blueprint, current_app, jsonify, request

from .db import (
    MAX_CONTENT_LENGTH,
    MAX_NAME_LENGTH,
    MAX_USER_ID_LENGTH,
    WINDOW_SECONDS,
    create_room,
    get_messages,
    get_room,
    is_member,
    join_room,
    leave_room,
    list_rooms,
    rate_limit_and_post,
)

bp = Blueprint("chat", __name__)


def _db():
    return current_app.config.get("DB_PATH")


# ── Rooms ─────────────────────────────────────────────────────────────────────

@bp.route("/rooms", methods=["POST"])
def create_room_route():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body must be JSON"}), 400
    missing = [f for f in ("name", "created_by") if not body.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    name = str(body["name"]).strip()
    created_by = str(body["created_by"]).strip()

    if not name:
        return jsonify({"error": "name must not be empty"}), 400
    if len(name) > MAX_NAME_LENGTH:
        return jsonify({"error": f"name exceeds {MAX_NAME_LENGTH} characters"}), 400
    if not created_by:
        return jsonify({"error": "created_by must not be empty"}), 400
    if len(created_by) > MAX_USER_ID_LENGTH:
        return jsonify({"error": f"created_by exceeds {MAX_USER_ID_LENGTH} characters"}), 400

    try:
        room = create_room(name, created_by, db_path=_db())
        return jsonify(room), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Room name '{name}' already exists"}), 409


@bp.route("/rooms", methods=["GET"])
def list_rooms_route():
    rooms = list_rooms(db_path=_db())
    return jsonify({"rooms": rooms}), 200


# ── Membership ────────────────────────────────────────────────────────────────

@bp.route("/rooms/<int:room_id>/join", methods=["POST"])
def join_room_route(room_id):
    body = request.get_json(silent=True)
    if not body or not str(body.get("user_id", "")).strip():
        return jsonify({"error": "Missing required field: user_id"}), 400

    user_id = str(body["user_id"]).strip()
    if len(user_id) > MAX_USER_ID_LENGTH:
        return jsonify({"error": f"user_id exceeds {MAX_USER_ID_LENGTH} characters"}), 400

    if get_room(room_id, db_path=_db()) is None:
        return jsonify({"error": f"Room {room_id} not found"}), 404
    joined = join_room(room_id, user_id, db_path=_db())
    return jsonify({"joined": joined}), 200


@bp.route("/rooms/<int:room_id>/leave", methods=["POST"])
def leave_room_route(room_id):
    body = request.get_json(silent=True)
    if not body or not str(body.get("user_id", "")).strip():
        return jsonify({"error": "Missing required field: user_id"}), 400

    user_id = str(body["user_id"]).strip()
    if get_room(room_id, db_path=_db()) is None:
        return jsonify({"error": f"Room {room_id} not found"}), 404
    left = leave_room(room_id, user_id, db_path=_db())
    return jsonify({"left": left}), 200


# ── Messages ──────────────────────────────────────────────────────────────────

@bp.route("/rooms/<int:room_id>/messages", methods=["POST"])
def post_message_route(room_id):
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body must be JSON"}), 400
    if "user_id" not in body or "content" not in body:
        return jsonify({"error": "Missing required fields: user_id, content"}), 400

    user_id = str(body["user_id"]).strip()
    content = str(body["content"])

    if not user_id:
        return jsonify({"error": "user_id must not be empty"}), 400
    if len(user_id) > MAX_USER_ID_LENGTH:
        return jsonify({"error": f"user_id exceeds {MAX_USER_ID_LENGTH} characters"}), 400
    if not content.strip():
        return jsonify({"error": "content must not be empty"}), 400
    if len(content) > MAX_CONTENT_LENGTH:
        return jsonify({"error": f"content exceeds {MAX_CONTENT_LENGTH} characters"}), 400

    if get_room(room_id, db_path=_db()) is None:
        return jsonify({"error": f"Room {room_id} not found"}), 404

    if not is_member(room_id, user_id, db_path=_db()):
        return jsonify({"error": "You must join the room before posting"}), 403

    # Atomically check rate limit and insert message in a single BEGIN IMMEDIATE transaction,
    # eliminating the TOCTOU gap between a separate check and insert.
    msg, allowed = rate_limit_and_post(room_id, user_id, content, db_path=_db())
    if not allowed:
        resp = jsonify({"error": "Rate limit exceeded. Try again later."})
        resp.headers["Retry-After"] = str(WINDOW_SECONDS)
        return resp, 429

    return jsonify(msg), 201


@bp.route("/rooms/<int:room_id>/messages", methods=["GET"])
def get_messages_route(room_id):
    if get_room(room_id, db_path=_db()) is None:
        return jsonify({"error": f"Room {room_id} not found"}), 404

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

    messages, next_cursor = get_messages(
        room_id, after_id=after_id, limit=limit, db_path=_db()
    )
    return jsonify({"messages": messages, "next_cursor": next_cursor}), 200
