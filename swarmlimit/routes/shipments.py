"""Shipments blueprint (shipment route agent).

``Blueprint('shipments', __name__)`` with NO ``url_prefix``; every route declares
its FULL absolute path exactly as written in the Route Table (spec §4). This
blueprint is NOT special: it simply declares routes under TWO roots
(``/orders/<int:oid>/shipments`` and ``/shipments/...``) -- no prefix.

Routes (spec §Route Table -> shipments; §3 validation; §6 auth):
  * ``POST /orders/<int:oid>/shipments`` -- admin. Creates the single shipment
    for the order; 404 if the order is absent, 409 ``conflict`` if the order
    already has a shipment (``UNIQUE(order_id)`` -> ``ValueError('shipment
    exists')``); 201 on create.
  * ``GET /shipments/<int:sid>`` -- role+own. ``get_shipment_for(sid, actor)``
    -> 404 for a non-owner (no 403, no existence leak).
  * ``POST /shipments/<int:sid>/advance`` -- admin. Body ``{to_status}``; the
    route validates ``to_status`` is a syntactically valid STORED status
    (``{pending, shipped, delivered, returned}``, else 400 ``validation``).
    Transition LEGALITY is decided by ``advance_shipment`` against
    ``LEGAL_TRANSITIONS``; an illegal transition (incl. every ``-> returned``)
    -> 409 ``conflict`` with status unchanged.

Envelope contract (spec §Error/response schema, §4): create / detail / advance
all return ``{"shipment": {...}}`` (incl. ``id`` and ``status``); errors go
through the shared ``error(code, status)`` helper -> ``{"error": code, ...}``.
Never a bare list/scalar.

Audit: ``record(...)`` is called POST-commit, route-level only, AFTER the model
call returns (never inside a transaction) -- for create and advance (spec §4).
"""

from flask import Blueprint, request

from swarmlimit import error
from swarmlimit.auth import current_user, login_required, role_required
from swarmlimit.models.audit_models import record
from swarmlimit.models.shipment_models import (
    advance_shipment,
    create_shipment,
    get_shipment,
    get_shipment_for,
)

bp = Blueprint("shipments", __name__)

# The four syntactically valid STORED shipment statuses. Any string outside this
# set is invalid INPUT (route -> 400); legality of a given transition is decided
# by ``advance_shipment`` (route -> 409), not here (spec §3).
VALID_STATUSES = {"pending", "shipped", "delivered", "returned"}


@bp.route("/orders/<int:oid>/shipments", methods=["POST"])
@role_required("admin")
def create_shipment_route(oid):
    """Create the single shipment for order ``oid`` (admin).

    404 if the order does not exist; 409 ``conflict`` if the order already has a
    shipment (``UNIQUE(order_id)`` -> ``ValueError('shipment exists')``). On
    success returns 201 ``{"shipment": {...}}`` and records an audit row
    post-commit.
    """
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return error("validation", 400)

    carrier = data.get("carrier")
    tracking = data.get("tracking")

    try:
        shipment_id = create_shipment(oid, carrier=carrier, tracking=tracking)
    except ValueError as exc:
        msg = str(exc)
        if msg == "order not found":
            return error("not_found", 404)
        # 'shipment exists' -> the order already has a shipment.
        return error("conflict", 409, message=msg)

    # Audit AFTER the class-A write committed (autocommit); never inside a tx.
    actor = current_user()
    record(actor["id"], "create", "shipment", shipment_id)

    return {"shipment": get_shipment(shipment_id)}, 201


@bp.route("/shipments/<int:sid>", methods=["GET"])
@login_required
def get_shipment_detail(sid):
    """Return shipment ``sid`` scoped to the current actor (role+own).

    ``get_shipment_for`` applies the ownership predicate in SQL: admin sees all;
    a customer sees only shipments transitively owned via their orders. A
    non-owner (or absent id) -> 0 rows -> ``None`` -> 404 ``not_found`` (no 403,
    no existence leak). ``login_required`` guarantees a non-``None`` actor.
    """
    shipment = get_shipment_for(sid, current_user())
    if shipment is None:
        return error("not_found", 404)
    return {"shipment": shipment}, 200


@bp.route("/shipments/<int:sid>/advance", methods=["POST"])
@role_required("admin")
def advance_shipment_route(sid):
    """Advance shipment ``sid`` to a new status (admin). Body ``{to_status}``.

    The route validates ONLY that ``to_status`` is a syntactically valid stored
    status (else 400 ``validation``). Transition LEGALITY is decided by
    ``advance_shipment`` against ``LEGAL_TRANSITIONS``: an illegal transition
    (incl. every ``-> returned``) raises ``ValueError('illegal transition')`` and
    leaves the status unchanged -> 409 ``conflict``. A shipment that does not
    exist -> 404. On success returns 200 ``{"shipment": {...}}`` and records an
    audit row post-commit.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("validation", 400)

    to_status = data.get("to_status")
    if to_status not in VALID_STATUSES:
        return error("validation", 400)

    try:
        advance_shipment(sid, to_status)
    except ValueError as exc:
        msg = str(exc)
        if msg == "shipment not found":
            return error("not_found", 404)
        # 'illegal transition' -> status unchanged.
        return error("conflict", 409, message=msg)

    # Audit AFTER the class-A write committed (autocommit); never inside a tx.
    actor = current_user()
    record(actor["id"], "advance", "shipment", sid)

    return {"shipment": get_shipment(sid)}, 200
