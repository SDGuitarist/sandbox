"""Search blueprint — GET /search?q=<query> for FTS5 prompt search.

Requires login. Users can only search their own prompts (filtered by
user_id from current_user). CSRF is not needed on GET search forms.
"""

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from app.database import get_db
from app.models.search_models import search_prompts

bp = Blueprint('search', __name__, url_prefix='/search')


@bp.route('/')
@login_required
def results():
    """Search prompts via FTS5.

    Query parameter:
        q (str): The search query. If empty or missing, renders the
                 search page with an empty results list.

    The search is scoped to the current user's prompts only — users
    cannot see other users' prompts in search results.
    """
    query = request.args.get('q', '').strip()

    with get_db() as conn:
        hits = search_prompts(conn, query, current_user.id)

    return render_template(
        'search/results.html',
        query=query,
        results=hits,
    )
