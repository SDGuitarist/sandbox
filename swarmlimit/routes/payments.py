"""Payments blueprint (payment route agent -- refund ledger, read-only).

``Blueprint('payments', __name__)`` with NO ``url_prefix``; every route declares
its FULL absolute path exactly as written in the Route Table (spec ``payments``).

Both routes are ``role+own`` reads governed by the Ownership-Scoped Getter
Contract (spec §Ownership-Scoped Getter Contract):

  * ``login_required`` wraps every view, so an anonymous request returns 401
    ``auth`` BEFORE any ``*_for(actor, ...)`` getter is reached. ``current_user()``
    is therefore GUARANTEED non-``None`` inside the view body.
  * Ownership is transitive through the order (a customer sees only payments
    whose order they own; admins see all) -- enforced as a SQL WHERE predicate
    inside the getter, never a post-fetch compare here.
  * A non-owner gets 0 rows -> ``None`` -> 404 ``not_found`` (no 403, no
    existence leak -- run-080 IDOR lesson).

This blueprint is READ-ONLY: no POST/PUT/PATCH/DELETE, no mutation, and no audit
``record(...)`` calls (``payments`` refund rows are written only by
``process_return`` in ``return_models``).
"""

from flask import Blueprint

from swarmlimit import error
from swarmlimit.auth import current_user, login_required
from swarmlimit.models.payment_models import get_payment_for, list_payments_for

bp = Blueprint("payments", __name__)


@bp.route("/payments", methods=["GET"])
@login_required
def list_payments():
    """List payments visible to the current user (role+own, transitive)."""
    payments = list_payments_for(current_user())
    return {"payments": payments}, 200


@bp.route("/payments/<int:pid>", methods=["GET"])
@login_required
def get_payment(pid):
    """Return one payment the current user owns, else 404 (no existence leak)."""
    payment = get_payment_for(pid, current_user())
    if payment is None:
        return error("not_found", 404)
    return {"payment": payment}, 200
