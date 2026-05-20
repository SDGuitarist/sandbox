from flask import Blueprint

bp = Blueprint('event_dashboard', __name__)

from . import routes  # noqa: E402, F401
