from flask import Blueprint

bp = Blueprint('goals', __name__)

from . import routes  # noqa: E402, F401
