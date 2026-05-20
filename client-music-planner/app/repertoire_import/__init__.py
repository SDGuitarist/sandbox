from flask import Blueprint

repertoire_import_bp = Blueprint(
    "repertoire_import",
    __name__,
    url_prefix="/repertoire/import",
)

from app.repertoire_import import routes  # noqa: E402, F401
