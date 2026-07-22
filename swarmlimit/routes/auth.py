"""Auth blueprint (auth-core).

``Blueprint('auth', __name__)`` with NO ``url_prefix``; every route declares its
FULL absolute path exactly as written in the Route Table (spec §4).

Pins enforced here:
  * ``POST /auth/register`` ALWAYS creates a ``customer`` (client-supplied
    ``role`` ignored/overridden); returns 201 with NO session established.
  * ``POST /auth/login`` returns 200 with ``csrf_token`` in the body on success.
  * ``POST /auth/logout`` requires auth; CSRF is enforced by the scaffold's
    global ``before_request`` (an authenticated mutating request without a valid
    ``X-CSRF-Token`` -> 400 ``csrf`` before this view runs).

Login/register are CSRF-exempt (no session yet) per App Configuration.
"""

from flask import Blueprint, request, session

from swarmlimit import error
from swarmlimit.auth import login_required, login_user, logout_user
from swarmlimit.models.auth_models import create_user, verify_credentials

bp = Blueprint("auth", __name__)


@bp.route("/auth/register", methods=["POST"])
def register():
    """Public registration -- ALWAYS creates a ``customer``.

    Ignores any client-supplied ``role`` (a client can NEVER self-register as
    admin -- the seeded ``admin@swarm.test`` is the sole bootstrap admin).
    Returns 201 with NO session (the client logs in separately).
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("validation", 400)

    email = data.get("email")
    password = data.get("password")
    name = data.get("name")

    if not isinstance(email, str) or not email or "@" not in email:
        return error("validation", 400)
    if not isinstance(password, str) or len(password) < 8:
        return error("validation", 400)
    if not isinstance(name, str) or not name:
        return error("validation", 400)

    try:
        user_id = create_user(
            email=email, password=password, role="customer", name=name
        )
    except ValueError as exc:
        # UNIQUE(email) collision -> duplicate registration.
        return error("conflict", 409, message=str(exc))

    return {"id": user_id}, 201


@bp.route("/auth/login", methods=["POST"])
def login():
    """Validate credentials and establish a session.

    On invalid input or bad credentials -> 401 ``auth`` with no field leak. On
    success -> 200 with ``csrf_token`` (minted by ``login_user``) in the body.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("auth", 401)

    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not email:
        return error("auth", 401)
    if not isinstance(password, str) or not password:
        return error("auth", 401)

    user = verify_credentials(email, password)
    if user is None:
        return error("auth", 401)

    login_user(user)
    return {
        "id": user["id"],
        "role": user["role"],
        "csrf_token": session["_csrf"],
    }, 200


@bp.route("/auth/logout", methods=["POST"])
@login_required
def logout():
    """Clear the session. Requires auth; CSRF enforced by scaffold before_request."""
    logout_user()
    return {"ok": True}, 200
