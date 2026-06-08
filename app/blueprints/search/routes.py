"""Search blueprint -- project-scoped full-text search over indexed entities.

Registered in the app factory as::

    from app.blueprints.search.routes import bp as search_bp
    app.register_blueprint(search_bp, url_prefix='/search')

The single route renders ``search/results.html`` for any project member.
"""

from flask import Blueprint, g, render_template, request

from app.blueprints.auth.routes import login_required, require_project_member
from app.database import get_db
from app.models.search_models import ENTITY_TYPE_LABELS, search

bp = Blueprint("search", __name__)


@bp.route("/<int:project_id>", methods=["GET"])
@login_required
@require_project_member
def search_page(project_id):
    """Render search results for ``?q=`` within the given project.

    ``require_project_member`` has already loaded ``g.project`` and ``g.member``
    and enforced membership (404 for unknown project, 403 for non-members). The
    query is sanitised inside ``search()``; an empty or operator-only query
    yields an empty result set rather than an error.
    """
    query = (request.args.get("q") or "").strip()
    conn = get_db()
    results = search(conn, query, project_id)
    return render_template(
        "search/results.html",
        project=g.project,
        query=query,
        results=results,
        entity_labels=ENTITY_TYPE_LABELS,
    )
