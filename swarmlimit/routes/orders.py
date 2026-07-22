"""Orders blueprint (order route agent).

``Blueprint('orders', __name__)`` with NO ``url_prefix``; every route declares
its FULL absolute path exactly as written in the Route Table (spec §4). JSON API
— success bodies are always a JSON object, errors go through the shared
``error(...)`` helper.

Routes (spec §Route Table → orders, §3, §6):
  * ``GET  /orders``            role+own — ``list_orders_for(current_user())``
    (customer → own, admin → all) → ``{"orders": [...]}``.
  * ``POST /orders``            auth     — ``create_order`` (owns its own
    ``transaction()``; this route NEVER manages a transaction). Validates
    ext_ref/items/qty/product_id; maps ``create_order``'s ValueErrors to
    409 ``conflict``; audits POST-commit. Returns 201 with ``{"order": {...}}``.
  * ``GET  /orders/<int:oid>``  role+own — ``get_order_for(oid, current_user())
    or error('not_found', 404)`` (404 for non-owner) → ``{"order": {...}}``.

``user_id`` resolution on ``POST /orders`` (spec §3/§6):
  * omitted → the current actor's id (both roles);
  * a customer is ALWAYS forced to their own id (any supplied ``user_id``
    ignored);
  * only an admin may pass an explicit ``user_id`` to place on another user's
    behalf.

Auth precedence (spec §6): ``login_required`` runs first, so an anonymous
request returns 401 ``auth`` before any ownership getter is reached; the scaffold
``before_request`` enforces CSRF (400 ``csrf``) only on authenticated mutating
requests. So an anonymous ``POST /orders`` returns 401, never 400.
"""

from flask import Blueprint, request

from swarmlimit import error
from swarmlimit.auth import current_user, login_required
from swarmlimit.models.audit_models import record
from swarmlimit.models.order_models import (
    create_order,
    get_order,
    get_order_for,
    list_orders_for,
)

bp = Blueprint("orders", __name__)


@bp.route("/orders", methods=["GET"])
@login_required
def list_orders_route():
    """List orders the actor may see (role+own).

    ``list_orders_for`` applies the ownership predicate in SQL (admin → all,
    customer → own), so no post-fetch filtering is needed. ``current_user()`` is
    guaranteed non-``None`` here (``login_required`` ran first).
    """
    orders = list_orders_for(current_user())
    return {"orders": orders}, 200


@bp.route("/orders", methods=["POST"])
@login_required
def create_order_route():
    """Create an order (auth). ``create_order`` owns its transaction.

    Validation (spec §3): body is a JSON object; ``ext_ref`` non-empty str;
    ``items`` a non-empty list where each item has an int ``product_id`` and an
    int ``qty > 0``. ``user_id`` resolution per the pin below. ``create_order``'s
    in-tx guards (ext_ref collision / insufficient stock / unavailable product)
    raise ``ValueError`` → mapped to 409 ``conflict``. Audit is recorded
    POST-commit (after ``create_order`` returns).
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("validation", 400)

    ext_ref = data.get("ext_ref")
    if not isinstance(ext_ref, str) or not ext_ref:
        return error("validation", 400)

    items = data.get("items")
    if not isinstance(items, list) or not items:
        return error("validation", 400)

    for item in items:
        if not isinstance(item, dict):
            return error("validation", 400)
        product_id = item.get("product_id")
        qty = item.get("qty")
        # bool is a subclass of int — reject it explicitly so ``True`` isn't a
        # valid product_id/qty.
        if not isinstance(product_id, int) or isinstance(product_id, bool):
            return error("validation", 400)
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            return error("validation", 400)

    actor = current_user()
    # user_id resolution: omitted → current actor's id (both roles); a customer
    # is ALWAYS forced to their own id (supplied user_id ignored); only an admin
    # may override with an explicit user_id.
    supplied_user_id = data.get("user_id")
    if actor["role"] == "admin" and supplied_user_id is not None:
        if not isinstance(supplied_user_id, int) or isinstance(supplied_user_id, bool):
            return error("validation", 400)
        user_id = supplied_user_id
    else:
        user_id = actor["id"]

    try:
        order_id = create_order(user_id, ext_ref, items)
    except ValueError as exc:
        # In-tx guards: ext_ref collision / insufficient stock / product
        # unavailable → 409 conflict.
        return error("conflict", 409, message=str(exc))

    # Audit POST-commit (after create_order has committed) — never inside a
    # transaction (spec §4).
    record(actor["id"], "create", "order", order_id)

    order = get_order(order_id)
    return {"order": order}, 201


@bp.route("/orders/<int:oid>", methods=["GET"])
@login_required
def get_order_route(oid):
    """Fetch a single order (role+own).

    ``get_order_for`` applies the ownership predicate in SQL; a non-owner (or a
    missing id) gets ``None`` → 404 ``not_found`` (no existence leak, run-080
    IDOR lesson). Includes ``items`` + ``total_cents``.
    """
    order = get_order_for(oid, current_user())
    if order is None:
        return error("not_found", 404)
    return {"order": order}, 200
