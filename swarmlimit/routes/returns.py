"""Returns blueprint (return route agent).

``Blueprint('returns', __name__)`` with NO ``url_prefix``; every route declares
its FULL absolute path exactly as written in the Route Table (spec §4). JSON API:
success bodies are always a JSON object; error bodies go through the shared
``error(...)`` helper.

Routes (spec Route Table §returns; auth modes per §6):
  * ``GET  /returns``           role+own -> ``list_returns_for(current_user())``.
  * ``POST /returns``           role+own on a BODY-supplied ``order_id`` -> the
    order is resolved via ``get_order_for(order_id, current_user())`` FIRST; a
    non-owner customer gets ``None`` -> **404** (no existence leak) BEFORE
    ``process_return`` runs (admin bypasses by role). Then ``process_return``
    OWNS its own transaction; its raised ``ValueError``s (ext_ref collision /
    shipment-not-delivered / refund-exceeds-original) map to **409 conflict**.
  * ``GET  /returns/<int:rid>``  role+own -> ``get_return_for(rid, actor)`` or 404.

Auth precedence (§6): every view is wrapped with ``login_required``, so an
anonymous request returns **401 auth** BEFORE any ownership getter is reached —
``current_user()`` is therefore GUARANTEED non-``None`` inside every body here.
CSRF (400) on the authenticated ``POST`` is enforced by the scaffold's global
``before_request`` before this view runs.

Validation (§3): ``ext_ref`` non-empty str; ``refund_cents`` a strictly-positive
int (``<= 0`` or non-int -> 400 ``validation``). ``reason`` is optional.

Audit (§4): ``record(...)`` is called exactly ONCE, POST-commit, at route level
AFTER ``process_return`` returns — NEVER inside the transaction.
"""

from flask import Blueprint, request

from swarmlimit import error
from swarmlimit.auth import current_user, login_required
from swarmlimit.models.audit_models import record
from swarmlimit.models.order_models import get_order_for
from swarmlimit.models.return_models import (
    get_return_for,
    list_returns_for,
    process_return,
)

bp = Blueprint("returns", __name__)


@bp.route("/returns", methods=["GET"])
@login_required
def list_returns_view():
    """List the actor's returns (role+own; admin -> all, customer -> own)."""
    actor = current_user()
    return {"returns": list_returns_for(actor)}, 200


@bp.route("/returns", methods=["POST"])
@login_required
def create_return_view():
    """Create a return for a body-supplied ``order_id`` (role+own on the body).

    Order of operations (mandatory, spec §6 / brief):
      1. Parse + validate the JSON body (400 ``validation`` on any bad input).
      2. Ownership PRE-CHECK: ``get_order_for(order_id, actor)``; ``None`` ->
         **404** (non-owner or absent order — no existence leak) BEFORE mutating.
      3. ``process_return`` (OWNS its transaction); map its ``ValueError``s to
         **409 conflict**.
      4. Audit POST-commit via ``record(...)`` (never inside the transaction).
    """
    actor = current_user()

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("validation", 400)

    order_id = data.get("order_id")
    ext_ref = data.get("ext_ref")
    reason = data.get("reason")
    refund_cents = data.get("refund_cents")

    # order_id: must be an int (bool is a subclass of int -> reject explicitly).
    if not isinstance(order_id, int) or isinstance(order_id, bool):
        return error("validation", 400)
    # ext_ref: non-empty string.
    if not isinstance(ext_ref, str) or not ext_ref:
        return error("validation", 400)
    # refund_cents: strictly-positive int (a return always refunds > 0).
    if not isinstance(refund_cents, int) or isinstance(refund_cents, bool):
        return error("validation", 400)
    if refund_cents <= 0:
        return error("validation", 400)
    # reason: optional; if supplied it must be a string.
    if reason is not None and not isinstance(reason, str):
        return error("validation", 400)

    # Ownership pre-check on the body-supplied order_id (404-not-403, no leak).
    # Admin sees all orders; a non-owner customer gets None -> 404 BEFORE any
    # mutation. This runs BEFORE process_return so a non-owner can never trigger
    # the transaction.
    if get_order_for(order_id, actor) is None:
        return error("not_found", 404)

    # process_return OWNS its transaction; the route just calls it and maps its
    # in-tx guard ValueErrors (ext_ref collision / shipment-not-delivered /
    # refund-exceeds-original) to 409 conflict.
    try:
        return_id = process_return(order_id, ext_ref, reason, refund_cents)
    except ValueError as exc:
        return error("conflict", 409, message=str(exc))

    # Audit POST-commit only (never inside the transaction).
    record(actor["id"], "return", "return", entity_id=return_id)

    created = get_return_for(return_id, actor)
    return {"return": created}, 201


@bp.route("/returns/<int:rid>", methods=["GET"])
@login_required
def get_return_view(rid):
    """Fetch one return by id (role+own); non-owner/absent -> 404 (no leak)."""
    actor = current_user()
    row = get_return_for(rid, actor)
    if row is None:
        return error("not_found", 404)
    return {"return": row}, 200
