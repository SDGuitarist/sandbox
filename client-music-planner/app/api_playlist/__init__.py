from flask import Blueprint

bp = Blueprint('api_playlist', __name__)

from . import routes  # noqa: E402, F401
