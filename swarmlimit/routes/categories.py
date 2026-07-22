"""Categories blueprint (category route agent).

``Blueprint('categories', __name__)`` with NO ``url_prefix``; every route
declares its FULL absolute path exactly as written in the Route Table (spec §4).

Auth (spec §6):
  * ``GET /categories`` and ``GET /categories/<int:cid>`` -> ``auth`` (any
    logged-in user may browse the catalog).
  * ``POST/PATCH/DELETE /categories`` -> ``admin`` only.

Response envelope (spec §4 / App Configuration):
  * list  -> ``{"categories": [...]}``
  * detail/create -> ``{"category": {...}}`` (the create response is 201)
  * every error body is produced by the shared ``error(code, status)`` helper
    -> ``{"error": code, ...}``. No route hand-rolls an error body.

Validation (spec §3):
  * POST: ``name`` non-empty -> else 400 ``validation``; duplicate name
    (UNIQUE -> ``ValueError``) -> 409 ``conflict``.
  * PATCH: ``name`` supplied AND non-empty -> else 400 ``validation``; 404 if the
    category is absent; duplicate name -> 409 ``conflict``.
  * DELETE: 404 if the category is absent; 409 ``conflict`` if referenced by a
    product (FK RESTRICT -> ``ValueError``).

Audit (spec §4): every create/update/delete view calls ``record(...)`` exactly
once, POST-commit and route-level -- never inside a transaction. The category
model writers are class-A (autocommit), so by the time these views call the
model function it has already committed.
"""

from flask import Blueprint, request

from swarmlimit import error
from swarmlimit.auth import current_user, login_required, role_required
from swarmlimit.models.audit_models import record
from swarmlimit.models.category_models import (
    create_category,
    delete_category,
    get_category,
    list_categories,
    update_category,
)

bp = Blueprint("categories", __name__)


@bp.route("/categories", methods=["GET"])
@login_required
def list_categories_view():
    """List all categories. Any logged-in user may browse (spec §6)."""
    return {"categories": list_categories()}, 200


@bp.route("/categories", methods=["POST"])
@role_required("admin")
def create_category_view():
    """Create a category (admin only).

    ``name`` must be a non-empty string (else 400 ``validation``). A duplicate
    name raises ``ValueError`` (UNIQUE) -> 409 ``conflict``. On success returns
    201 with the created category detail; audits POST-commit.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("validation", 400)

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return error("validation", 400)

    try:
        category_id = create_category(name)
    except ValueError:
        return error("conflict", 409)

    record(current_user()["id"], "create", "category", category_id)
    return {"category": get_category(category_id)}, 201


@bp.route("/categories/<int:cid>", methods=["GET"])
@login_required
def get_category_view(cid):
    """Return one category, or 404 if absent. Any logged-in user (spec §6)."""
    category = get_category(cid)
    if category is None:
        return error("not_found", 404)
    return {"category": category}, 200


@bp.route("/categories/<int:cid>", methods=["PATCH"])
@role_required("admin")
def update_category_view(cid):
    """Update a category's name (admin only).

    ``name`` must be supplied AND a non-empty string (else 400 ``validation``);
    404 if the category is absent; a duplicate name raises ``ValueError``
    (UNIQUE) -> 409 ``conflict``. Audits POST-commit.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("validation", 400)

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return error("validation", 400)

    if get_category(cid) is None:
        return error("not_found", 404)

    try:
        update_category(cid, name=name)
    except ValueError:
        return error("conflict", 409)

    record(current_user()["id"], "update", "category", cid)
    return {"category": get_category(cid)}, 200


@bp.route("/categories/<int:cid>", methods=["DELETE"])
@role_required("admin")
def delete_category_view(cid):
    """Delete a category (admin only).

    404 if the category is absent; 409 ``conflict`` if any product references it
    (FK RESTRICT via ``product_categories.category_id`` -> ``ValueError``).
    Audits POST-commit.
    """
    if get_category(cid) is None:
        return error("not_found", 404)

    try:
        delete_category(cid)
    except ValueError:
        return error("conflict", 409)

    record(current_user()["id"], "delete", "category", cid)
    return {"ok": True}, 200
