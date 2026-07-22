"""Suppliers blueprint (supplier route agent).

``Blueprint('suppliers', __name__)`` with NO ``url_prefix``; every route declares
its FULL absolute path exactly as written in the Route Table (spec §Route Table →
suppliers) so ``request.url_rule.rule`` == the manifest path and no trailing-slash
collection rule is ever registered (spec §4 / P0-3).

Auth (spec §6 Authorization Matrix):
  * ``GET`` (list + detail) -> ``login_required`` (any logged-in may browse).
  * ``POST`` / ``PATCH`` / ``DELETE`` -> ``role_required('admin')`` (admin only).
    ``role_required`` alone yields 401-before-403 (anonymous -> 401 ``auth``,
    authenticated wrong-role -> 403 ``forbidden``) per its pinned two-branch
    contract; CSRF (400) is enforced by the scaffold ``before_request`` only for
    already-authenticated mutating requests, so it never precedes the 401.

Validation (spec §3 Input Validation Prescriptions):
  * ``POST /suppliers`` -> ``name`` non-empty else 400 ``validation``.
  * ``PATCH /suppliers/<sid>`` -> at least one whitelisted field; ``active`` in
    {0,1}; 400 ``validation`` on bad input, 404 ``not_found`` if the supplier is
    absent.
  * ``DELETE /suppliers/<sid>`` -> 404 if absent; 409 ``conflict`` if products
    reference it (FK RESTRICT -> ``ValueError`` from the model).

Response envelope (spec §App-Config Error/response schema, H4):
  * list  -> ``{"suppliers": [...]}`` (object, never a bare list).
  * create + detail -> ``{"supplier": {...incl "id"}}``; create returns 201.
  * errors -> ``error(code, status)`` -> ``{"error": code, ...}``.

Audit (spec §4 / audit_models.record): every create/update/delete calls
``record(...)`` exactly ONCE, POST-commit (after the class-A model call has
returned and autocommitted), never inside a transaction.
"""

from flask import Blueprint, request

from swarmlimit import error
from swarmlimit.auth import current_user, login_required, role_required
from swarmlimit.models.audit_models import record
from swarmlimit.models.supplier_models import (
    create_supplier,
    delete_supplier,
    get_supplier,
    list_suppliers,
    update_supplier,
)

bp = Blueprint("suppliers", __name__)

# Fields a PATCH may set (mirrors supplier_models._UPDATE_WHITELIST / spec §3).
_PATCH_WHITELIST = ("name", "contact_email", "active")


@bp.route("/suppliers", methods=["GET"])
@login_required
def list_suppliers_view():
    """List every supplier. Auth: any logged-in user (spec §6)."""
    return {"suppliers": list_suppliers()}, 200


@bp.route("/suppliers", methods=["POST"])
@role_required("admin")
def create_supplier_view():
    """Create a supplier (admin only). ``name`` required non-empty (spec §3).

    On success returns 201 ``{"supplier": {...incl "id"}}`` and records one audit
    row POST-commit (the model is class-A: it autocommits before returning).
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("validation", 400)

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return error("validation", 400)

    contact_email = data.get("contact_email")
    if contact_email is not None and not isinstance(contact_email, str):
        return error("validation", 400)

    supplier_id = create_supplier(name=name, contact_email=contact_email)

    # POST-commit audit (class-A model already persisted; never inside a tx).
    record(current_user()["id"], "create", "supplier", entity_id=supplier_id)

    supplier = get_supplier(supplier_id)
    return {"supplier": supplier}, 201


@bp.route("/suppliers/<int:sid>", methods=["GET"])
@login_required
def get_supplier_view(sid):
    """Fetch one supplier. Auth: any logged-in user. 404 if absent (spec §6/§3)."""
    supplier = get_supplier(sid)
    if supplier is None:
        return error("not_found", 404)
    return {"supplier": supplier}, 200


@bp.route("/suppliers/<int:sid>", methods=["PATCH"])
@role_required("admin")
def update_supplier_view(sid):
    """Update whitelisted supplier fields (admin only).

    Requires at least one whitelisted field; ``active`` must be in {0,1}
    (spec §3). 404 if the supplier is absent (checked BEFORE the write so the
    audit row is not recorded for a no-op). Records one audit row POST-commit.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("validation", 400)

    fields = {k: data[k] for k in _PATCH_WHITELIST if k in data}
    if not fields:
        return error("validation", 400)

    if "name" in fields and (
        not isinstance(fields["name"], str) or not fields["name"].strip()
    ):
        return error("validation", 400)

    if "contact_email" in fields and not (
        fields["contact_email"] is None or isinstance(fields["contact_email"], str)
    ):
        return error("validation", 400)

    if "active" in fields:
        active = fields["active"]
        # Reject bools (isinstance(True, int) is True) and any value not in {0,1}.
        if isinstance(active, bool) or not isinstance(active, int) or active not in (0, 1):
            return error("validation", 400)

    if get_supplier(sid) is None:
        return error("not_found", 404)

    update_supplier(sid, **fields)

    # POST-commit audit (class-A model already persisted).
    record(current_user()["id"], "update", "supplier", entity_id=sid)

    return {"supplier": get_supplier(sid)}, 200


@bp.route("/suppliers/<int:sid>", methods=["DELETE"])
@role_required("admin")
def delete_supplier_view(sid):
    """Hard-delete a supplier (admin only).

    404 if absent. 409 ``conflict`` if any product references it — the model
    relies on FK ``ON DELETE RESTRICT`` and re-raises the ``IntegrityError`` as
    ``ValueError`` (spec §3); nothing is deleted in that case. Records one audit
    row POST-commit on a successful delete.
    """
    if get_supplier(sid) is None:
        return error("not_found", 404)

    try:
        delete_supplier(sid)
    except ValueError:
        # products.supplier_id FK RESTRICT -> supplier in use.
        return error("conflict", 409)

    # POST-commit audit (class-A model already persisted).
    record(current_user()["id"], "delete", "supplier", entity_id=sid)

    return {"deleted": sid}, 200
