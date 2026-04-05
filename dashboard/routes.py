import sqlite3

from flask import Blueprint, current_app, jsonify, request

from .auth import require_auth
from .db import get_db
from .events import append_event, list_events
from .health import list_results
from .jobs import enqueue_job
from .keys import create_key, list_keys, revoke_key
from .services import (
    create_service, delete_service, get_dashboard, get_service, list_services
)
from .ssrf import SSRFError, validate_url

bp = Blueprint("dashboard", __name__)


def _db():
    return current_app.config.get("DB_PATH")


# ── Services ──────────────────────────────────────────────────────────────────

@bp.route("/services", methods=["POST"])
@require_auth
def create_service_route():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body must be JSON"}), 400

    name = str(body.get("name", "")).strip()
    health_check_url = str(body.get("health_check_url", "")).strip()

    if not name:
        return jsonify({"error": "Missing required field: name"}), 400
    if not health_check_url:
        return jsonify({"error": "Missing required field: health_check_url"}), 400

    try:
        validate_url(health_check_url)
    except (SSRFError, ValueError) as e:
        return jsonify({"error": str(e)}), 422

    try:
        with get_db(path=_db(), immediate=True) as conn:
            service = create_service(
                conn,
                name=name,
                health_check_url=health_check_url,
                url=body.get("url"),
                description=body.get("description"),
            )
            append_event(conn, "service.registered", service_id=service["id"],
                         payload={"name": name})
        return jsonify(service), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Service name '{name}' already exists"}), 409


@bp.route("/services", methods=["GET"])
def list_services_route():
    with get_db(path=_db()) as conn:
        services = list_services(conn)
    return jsonify({"services": services}), 200


@bp.route("/services/<service_id>", methods=["GET"])
def get_service_route(service_id):
    with get_db(path=_db()) as conn:
        service = get_service(conn, service_id)
        if service is None:
            return jsonify({"error": f"Service '{service_id}' not found"}), 404
        history = list_results(conn, service_id)
    service["health_history"] = history
    return jsonify(service), 200


@bp.route("/services/<service_id>", methods=["DELETE"])
@require_auth
def delete_service_route(service_id):
    with get_db(path=_db(), immediate=True) as conn:
        service = get_service(conn, service_id)
        if service is None:
            return jsonify({"error": f"Service '{service_id}' not found"}), 404
        append_event(conn, "service.deleted", service_id=service_id,
                     payload={"name": service["name"]})
        delete_service(conn, service_id)
    return "", 204


@bp.route("/services/<service_id>/check", methods=["POST"])
@require_auth
def trigger_check_route(service_id):
    with get_db(path=_db(), immediate=True) as conn:
        service = get_service(conn, service_id)
        if service is None:
            return jsonify({"error": f"Service '{service_id}' not found"}), 404
        job = enqueue_job(conn, service_id)
    return jsonify({"job_id": job["id"], "service_id": service_id, "status": "queued"}), 202


# ── Dashboard ─────────────────────────────────────────────────────────────────

@bp.route("/dashboard", methods=["GET"])
def dashboard_route():
    with get_db(path=_db()) as conn:
        data = get_dashboard(conn)
    return jsonify({"services": data}), 200


# ── API Keys ──────────────────────────────────────────────────────────────────

@bp.route("/keys", methods=["POST"])
@require_auth
def create_key_route():
    body = request.get_json(silent=True) or {}
    label = str(body.get("label", "")).strip()
    if not label:
        return jsonify({"error": "Missing required field: label"}), 400

    service_id = body.get("service_id")

    with get_db(path=_db(), immediate=True) as conn:
        if service_id:
            if get_service(conn, service_id) is None:
                return jsonify({"error": f"Service '{service_id}' not found"}), 404
        key = create_key(conn, label=label, service_id=service_id)
        append_event(conn, "key.created", service_id=service_id,
                     payload={"label": label, "prefix": key["prefix"]})
    return jsonify(key), 201


@bp.route("/keys", methods=["GET"])
@require_auth
def list_keys_route():
    service_id = request.args.get("service_id")
    with get_db(path=_db()) as conn:
        keys = list_keys(conn, service_id=service_id)
    return jsonify({"keys": keys}), 200


@bp.route("/keys/<key_id>", methods=["DELETE"])
@require_auth
def revoke_key_route(key_id):
    with get_db(path=_db(), immediate=True) as conn:
        if not revoke_key(conn, key_id):
            return jsonify({"error": f"Key '{key_id}' not found or already revoked"}), 404
        append_event(conn, "key.revoked", payload={"key_id": key_id})
    return "", 204


# ── Events ────────────────────────────────────────────────────────────────────

@bp.route("/events", methods=["GET"])
def events_route():
    try:
        after_id = int(request.args["after"]) if "after" in request.args else None
        limit = int(request.args.get("limit", 20))
        limit = max(1, min(limit, 200))
    except (ValueError, TypeError):
        return jsonify({"error": "after and limit must be integers"}), 400

    service_id = request.args.get("service_id")

    with get_db(path=_db()) as conn:
        result = list_events(conn, after_id=after_id, limit=limit, service_id=service_id)
    return jsonify(result), 200
