"""swarmlimit application factory (scaffold agent).

Owns: create_app (MODULE-LEVEL, FC50 orchestration entrypoint), the shared
error(...) response helper, blueprint registration (fixed order), the CSRF
header-token before_request, the static CSP response header, one-time init_db
on absent DB file, and the admin GET /audit view (scaffold-hosted, no blueprint).

Pure JSON API — no Jinja/templates. See the shared-interface spec
(docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md).
"""

import logging
import os

from flask import Flask, g, jsonify, request, session

logger = logging.getLogger(__name__)

# Fixed dev fallback secret (development ONLY; production fails closed if unset).
_DEV_SECRET_KEY = "swarmlimit-dev-insecure-key"

# Mutating HTTP methods subject to CSRF header-token checking.
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def error(code: str, status: int, **extra) -> tuple[dict, int]:
    """Shared error-envelope helper (FC50 orchestration entrypoint).

    Returns ``({"error": code, **extra}, status)`` — the ONE error body shape
    every route imports (`from swarmlimit import error`). No route hand-rolls an
    error body. Canonical codes: "validation" (400), "csrf" (400), "auth" (401),
    "forbidden" (403), "not_found" (404), "conflict" (409).
    """
    body = {"error": code}
    body.update(extra)
    return body, status


def create_app(config=None):
    """Application factory (module level — FC50 orchestration entrypoint).

    No module-level ``app = create_app()`` is created at import time, so importing
    the package never side-effects the DB. Smoke builds its own app against a
    throwaway temp DB whose file does not yet exist (so init_db runs once).
    """
    app = Flask(__name__)

    # --- SECRET_KEY (fail-closed outside development) ---
    flask_env = os.environ.get("FLASK_ENV")
    is_development = flask_env == "development"
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        if not is_development:
            raise RuntimeError(
                "SECRET_KEY is required when FLASK_ENV != 'development' "
                "(refusing to start with an insecure default in a non-dev environment)."
            )
        logger.warning(
            "SECRET_KEY unset; falling back to a fixed insecure development key "
            "because FLASK_ENV == 'development'. Do NOT use this in production."
        )
        secret_key = _DEV_SECRET_KEY
    app.config["SECRET_KEY"] = secret_key

    # --- Session cookie hardening ---
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = not is_development

    # --- Optional test/caller config overrides (e.g. smoke's DB path) ---
    if config:
        app.config.update(config)

    # --- One-time schema init: only when the DB file is absent ---
    # Imported here (not at module top) so the package can be byte-compiled and
    # partially imported before the database agent's module resolves at assembly.
    from swarmlimit.database import init_db

    db_path = app.config.get("DATABASE")
    if db_path is None or not os.path.exists(db_path):
        init_db()

    # --- CSRF header-token guard (authenticated mutating requests only) ---
    @app.before_request
    def _csrf_protect():
        # GET (and other non-mutating methods) are exempt.
        if request.method not in _MUTATING_METHODS:
            return None
        # Login/register are exempt (no session established yet).
        if request.endpoint in ("auth.login", "auth.register"):
            return None
        # Auth precedes CSRF: an anonymous request has no session token, so we do
        # NOT reject it here — it falls through to the view's login_required and
        # returns 401 `auth`. CSRF applies ONLY to authenticated mutating requests.
        expected = session.get("_csrf")
        if expected is None:
            return None
        supplied = request.headers.get("X-CSRF-Token")
        if supplied != expected:
            body, status = error("csrf", 400)
            return jsonify(body), status
        return None

    # --- Static CSP header on every response (JSON API serves no HTML/JS) ---
    @app.after_request
    def _set_csp(response):
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        return response

    # --- Blueprint registration (FIXED order) ---
    from swarmlimit.routes.auth import bp as auth_bp
    from swarmlimit.routes.suppliers import bp as suppliers_bp
    from swarmlimit.routes.categories import bp as categories_bp
    from swarmlimit.routes.products import bp as products_bp
    from swarmlimit.routes.orders import bp as orders_bp
    from swarmlimit.routes.shipments import bp as shipments_bp
    from swarmlimit.routes.returns import bp as returns_bp
    from swarmlimit.routes.payments import bp as payments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(shipments_bp)
    app.register_blueprint(returns_bp)
    app.register_blueprint(payments_bp)

    # --- Admin GET /audit view (scaffold-hosted; no blueprint) ---
    from swarmlimit.auth import role_required
    from swarmlimit.models.audit_models import list_audit

    @app.route("/audit", methods=["GET"])
    @role_required("admin")
    def audit_view():
        entity_type = request.args.get("entity_type")
        rows = list_audit(entity_type=entity_type)
        return jsonify({"audit": rows}), 200

    return app
