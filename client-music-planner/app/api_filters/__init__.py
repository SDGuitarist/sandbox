from flask import Blueprint

bp = Blueprint('api_filters', __name__)

from . import routes  # noqa: E402, F401
