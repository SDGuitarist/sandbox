from flask import Blueprint

bp = Blueprint('revenue', __name__)

from . import routes  # noqa: E402, F401
