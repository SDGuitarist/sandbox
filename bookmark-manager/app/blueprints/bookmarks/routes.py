import math
from urllib.parse import urlparse

from flask import abort, flash, redirect, render_template, request, url_for

from app.blueprints.bookmarks import bookmarks_bp
from app.db import get_db
from app.fetch_title import fetch_page_title
from app.models import (
    ITEMS_PER_PAGE,
    SORT_LABELS,
    SORT_OPTIONS,
    create_bookmark,
    delete_bookmark,
    cleanup_orphan_tags,
    get_all_bookmarks,
    get_bookmark,
    get_bookmark_count,
    get_bookmarks_by_url,
    get_tags_for_bookmark,
    get_tags_for_bookmarks,
    search_bookmark_count,
    search_bookmarks,
    set_bookmark_tags,
    update_bookmark,
)


def validate_url(url: str) -> str:
    """Validate and return cleaned URL. Raises ValueError on failure."""
    url = url.strip()
    if not url:
        raise ValueError("URL is required")
    if len(url) > 2048:
        raise ValueError("URL must be 2048 characters or less")
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError("URL must start with http:// or https://")
    if not parsed.netloc:
        raise ValueError("Invalid URL")
    return url


@bookmarks_bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    sort_order = request.args.get('sort', 'newest')
    if sort_order not in SORT_OPTIONS:
        sort_order = 'newest'
    query = request.args.get('q', '').strip()

    with get_db() as conn:
        if query:
            count = search_bookmark_count(conn, query)
            total_pages = math.ceil(count / ITEMS_PER_PAGE)
            if page > total_pages and total_pages > 0:
                return redirect(url_for('bookmarks.index', q=query, sort=sort_order, page=1))
            offset = (page - 1) * ITEMS_PER_PAGE
            bookmarks = search_bookmarks(conn, query, sort_order=sort_order, limit=ITEMS_PER_PAGE, offset=offset)
        else:
            count = get_bookmark_count(conn)
            total_pages = math.ceil(count / ITEMS_PER_PAGE)
            if page > total_pages and total_pages > 0:
                return redirect(url_for('bookmarks.index', sort=sort_order, page=1))
            offset = (page - 1) * ITEMS_PER_PAGE
            bookmarks = get_all_bookmarks(conn, sort_order=sort_order, limit=ITEMS_PER_PAGE, offset=offset)

        bookmark_tags = get_tags_for_bookmarks(conn, [b['id'] for b in bookmarks])

    return render_template(
        'bookmarks/list.html',
        bookmarks=bookmarks,
        page=page,
        total_pages=total_pages,
        query=query,
        tag_filter='',
        sort_order=sort_order,
        bookmark_tags=bookmark_tags,
        sort_options=SORT_LABELS,
    )


@bookmarks_bp.route('/new')
def new_bookmark():
    return render_template('bookmarks/form.html', bookmark=None, tags_str='', is_edit=False)


@bookmarks_bp.route('/new', methods=['POST'])
def create_bookmark_route():
    url = request.form.get('url', '')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    tags_raw = request.form.get('tags', '')
    tag_names = [t.strip() for t in tags_raw.split(',') if t.strip()]

    try:
        url = validate_url(url)
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('bookmarks.new_bookmark'))

    if not title:
        title = fetch_page_title(url)

    with get_db(immediate=True) as conn:
        existing = get_bookmarks_by_url(conn, url)
        if existing:
            flash("You already have this URL bookmarked", 'warning')

        bookmark_id = create_bookmark(conn, url, title or '', description)
        set_bookmark_tags(conn, bookmark_id, tag_names)

    flash("Bookmark created successfully", 'success')
    return redirect(url_for('bookmarks.index'))


@bookmarks_bp.route('/<int:id>/edit')
def edit_bookmark(id):
    with get_db() as conn:
        bookmark = get_bookmark(conn, id)
        if bookmark is None:
            abort(404)
        tags = get_tags_for_bookmark(conn, id)

    tags_str = ', '.join(t['name'] for t in tags)
    return render_template('bookmarks/form.html', bookmark=bookmark, tags_str=tags_str, is_edit=True)


@bookmarks_bp.route('/<int:id>/edit', methods=['POST'])
def update_bookmark_route(id):
    url = request.form.get('url', '')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    tags_raw = request.form.get('tags', '')
    tag_names = [t.strip() for t in tags_raw.split(',') if t.strip()]

    try:
        url = validate_url(url)
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('bookmarks.edit_bookmark', id=id))

    with get_db(immediate=True) as conn:
        update_bookmark(conn, id, url, title, description)
        set_bookmark_tags(conn, id, tag_names)

    flash("Bookmark updated successfully", 'success')
    return redirect(url_for('bookmarks.show_bookmark', id=id))


@bookmarks_bp.route('/<int:id>/delete', methods=['POST'])
def delete_bookmark_route(id):
    with get_db(immediate=True) as conn:
        delete_bookmark(conn, id)
        cleanup_orphan_tags(conn)

    flash("Bookmark deleted successfully", 'success')
    return redirect(url_for('bookmarks.index'))


@bookmarks_bp.route('/<int:id>')
def show_bookmark(id):
    with get_db() as conn:
        bookmark = get_bookmark(conn, id)
        if bookmark is None:
            abort(404)
        tags = get_tags_for_bookmark(conn, id)

    return render_template('bookmarks/detail.html', bookmark=bookmark, tags=tags)
