from flask import Blueprint

bp = Blueprint('repertoire', __name__)

from . import routes  # noqa: E402, F401
