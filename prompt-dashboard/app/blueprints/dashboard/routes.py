from flask import Blueprint, render_template, request

from app.database import get_db
from app.models import get_all_prompts, get_all_tags, get_dashboard_stats

bp = Blueprint('dashboard', __name__, url_prefix='/')


@bp.route('/')
def index():
    """Dashboard index — lists all prompts with FTS5 search and tag filtering."""
    search_query = request.args.get('q')
    tag_name = request.args.get('tag')

    with get_db() as conn:
        return render_template(
            'dashboard/index.html',
            prompts=get_all_prompts(conn, search_query, tag_name),
            tags=get_all_tags(conn),
            stats=get_dashboard_stats(conn),
            search_query=search_query,
            selected_tag=tag_name,
        )
