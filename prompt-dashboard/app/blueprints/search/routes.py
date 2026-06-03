"""Search blueprint — GET /search?q=<query> for FTS5 prompt search."""
from flask import Blueprint, g, render_template, request

from app.auth_helpers import login_required
from app.database import get_db
from app.models.search_models import search_prompts

bp = Blueprint('search', __name__)


@bp.route('/')
@login_required
def search_page():
    query = request.args.get('q', '').strip()[:200]
    conn = get_db()
    results = search_prompts(conn, query, g.user['id']) if query else []
    return render_template('search/results.html', query=query, results=results)
