"""Decorators & session helpers (auth-core -- NOT a model).

This module owns the session lifecycle (``login_user`` / ``logout_user`` /
``current_user``) and the two access-control decorators (``login_required`` /
``role_required``) that every route agent imports. It is a pure JSON API, so
guards return JSON error envelopes via ``error(...)`` (never a redirect).

It ALSO documents -- but does NOT implement -- the Ownership-Scoped Getter
Contract (see the module-level docstring block below). The per-resource
``get_<x>_for`` / ``list_<x>_for`` getters are implemented by the Wave-1 model
agents (order/shipment/return/payment); auth-core only defines the uniform rule
they all obey.

Ownership-Scoped Getter Contract (UNIFORM across all owning agents -- order,
shipment, return, payment; run-080 IDOR lesson):

  * Signatures: ``get_<x>_for(<id>, actor) -> dict | None`` and
    ``list_<x>_for(actor, **filters) -> list[dict]``. ``actor`` is the
    ``current_user()`` dict (``{id, role, ...}``) and is ALWAYS the trailing arg
    on single-row getters.
  * The ownership check is a **SQL WHERE predicate in the query**, never a
    fetch-then-compare in Python.
  * ``actor['role'] == 'admin'`` -> no ownership restriction (admin sees all).
  * ``actor['role'] == 'customer'`` -> restrict to rows the customer owns. For
    ``orders`` (the ownership root) the predicate is
    ``orders.user_id = :actor_id``. For derived resources (shipments, returns,
    payments) ownership is transitive through the order:
    ``EXISTS (SELECT 1 FROM orders o WHERE o.id = <x>.order_id
    AND o.user_id = :actor_id)``.
  * A non-owner therefore gets 0 rows -> ``None`` / ``[]``; the route does
    ``row = get_<x>_for(...) or error('not_found', 404)``. No 403, no existence
    leak on reads.
  * Anonymous guard precedes the getter: every ``role+own`` view is wrapped with
    ``login_required`` (an anonymous request returns 401 ``auth`` BEFORE any
    ``*_for(actor, ...)`` getter runs), and every ownership getter is called with
    ``current_user()`` -- which is therefore GUARANTEED non-``None`` inside the
    view body, so ``actor['role']`` / ``actor['id']`` cannot fail.
"""

from functools import wraps
from secrets import token_urlsafe

from flask import g, session

from swarmlimit import error
from swarmlimit.models.auth_models import get_user


def login_user(user):
    """Establish a session for ``user`` and mint the CSRF token.

    Stores the user id under ``session['user_id']`` and mints a fresh CSRF token
    under ``session['_csrf']`` (returned to the client in the login response
    body as ``csrf_token`` and required on every subsequent authenticated
    mutating request). Clears any cached ``current_user`` on ``g``.
    """
    session["user_id"] = user["id"]
    session["_csrf"] = token_urlsafe(32)
    g.pop("current_user", None)


def logout_user():
    """Clear the session and any cached user on ``g``."""
    session.pop("user_id", None)
    session.pop("_csrf", None)
    g.pop("current_user", None)


def current_user():
    """Return the logged-in user row as a dict, or None if anonymous.

    Cached on ``g`` for the duration of the request so repeated calls (e.g.
    ``login_required`` then ``role_required`` then the view body) hit the DB at
    most once. A stale ``session['user_id']`` (user deleted) resolves to None.
    """
    if "current_user" in g:
        return g.current_user
    user = None
    user_id = session.get("user_id")
    if user_id is not None:
        user = get_user(user_id)
    g.current_user = user
    return user


def login_required(view):
    """Reject anonymous callers with 401 ``auth`` (JSON API -- no redirect)."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return error("auth", 401)
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    """Restrict a view to the given roles with a pinned two-branch contract.

    Does NOT rely on decorator stacking order:

      * ``current_user()`` is None (anonymous) -> 401 ``auth``.
      * ONLY if authenticated AND ``current_user()['role']`` not in ``roles``
        -> 403 ``forbidden``.

    So an anonymous request to a role-gated route ALWAYS returns 401 (never 403,
    and never a ``None['role']`` crash), whether or not ``login_required`` is
    also stacked. This makes the anonymous-401 / authenticated-wrong-role-403
    outcome deterministic at the decorator layer, guaranteeing 401 precedes 403.
    """

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                return error("auth", 401)
            if user["role"] not in roles:
                return error("forbidden", 403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
