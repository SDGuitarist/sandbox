"""API key authentication middleware for the dashboard."""
from functools import wraps

from flask import current_app, g, jsonify, request

from .db import get_db
from .keys import validate_key


def require_auth(f):
    """Decorator that validates the Authorization: Bearer <key> header.

    On success: injects g.api_key = {id, label, service_id}.
    On failure: returns 401.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        raw_key = auth_header[len("Bearer "):]
        db_path = current_app.config.get("DB_PATH")

        with get_db(path=db_path, immediate=True) as conn:
            key_info = validate_key(conn, raw_key)

        if key_info is None:
            return jsonify({"error": "Invalid or revoked API key"}), 401

        g.api_key = key_info
        return f(*args, **kwargs)

    return wrapper
