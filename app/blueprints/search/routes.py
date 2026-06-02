"""Search blueprint -- FTS5 full-text search across scenes, cast, crew, locations."""

from flask import Blueprint, render_template, request

from app.blueprints.auth.routes import login_required, require_project_member
from app.database import get_db
from app.models.search_models import search

bp = Blueprint('search', __name__)


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def search_page(project_id):
    """GET /search/<project_id>?q=query -- search across project entities."""
    query = request.args.get('q', '').strip()
    results = []

    if query:
        conn = get_db()
        results = search(conn, query, project_id)

    return render_template(
        'search/results.html',
        query=query,
        results=results,
        project_id=project_id,
    )
