from flask import Blueprint

bp = Blueprint('portal_playlist', __name__)

from . import routes  # noqa: E402, F401
