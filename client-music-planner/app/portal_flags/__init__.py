from flask import Blueprint

bp = Blueprint('portal_flags', __name__)

from . import routes  # noqa: E402, F401
