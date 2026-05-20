from flask import Blueprint

bp = Blueprint('repertoire_import', __name__)

from . import routes  # noqa: E402, F401
