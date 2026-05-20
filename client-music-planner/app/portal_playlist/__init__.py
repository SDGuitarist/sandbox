from flask import Blueprint

bp = Blueprint('portal_playlist', __name__, url_prefix='/portal')

from . import routes  # noqa: E402, F401
