import math

from flask import redirect, render_template, request, url_for

from app.blueprints.tags import tags_bp
from app.db import get_db
from app.models import (
    ITEMS_PER_PAGE,
    SORT_LABELS,
    get_all_tags,
    get_bookmarks_by_tag,
    get_bookmarks_by_tag_count,
    get_tags_for_bookmarks,
)


@tags_bp.route('/')
def index():
    with get_db() as conn:
        tags = get_all_tags(conn)

    return render_template('tags/list.html', tags=tags)


@tags_bp.route('/<name>')
def show(name):
    page = request.args.get('page', 1, type=int)
    sort_order = request.args.get('sort', 'newest')

    with get_db() as conn:
        count = get_bookmarks_by_tag_count(conn, name)
        total_pages = math.ceil(count / ITEMS_PER_PAGE)
        if page > total_pages and total_pages > 0:
            return redirect(url_for('tags.show', name=name, sort=sort_order, page=1))
        offset = (page - 1) * ITEMS_PER_PAGE
        bookmarks = get_bookmarks_by_tag(conn, name, sort_order=sort_order, limit=ITEMS_PER_PAGE, offset=offset)
        bookmark_tags = get_tags_for_bookmarks(conn, [b['id'] for b in bookmarks])

    return render_template(
        'bookmarks/list.html',
        bookmarks=bookmarks,
        page=page,
        total_pages=total_pages,
        query='',
        tag_filter=name,
        sort_order=sort_order,
        bookmark_tags=bookmark_tags,
        sort_options=SORT_LABELS,
    )
